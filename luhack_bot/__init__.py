import logging
import sys
from textwrap import dedent

from cryptography.fernet import Fernet


def run():
    """Run the bot."""
    from luhack_bot import bot

    ch = logging.StreamHandler(sys.stderr)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    ch.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

    logger.info("Starting up bot")

    bot.start()

    logger.info("Bot shutting down")


def gen_tokens():
    """Generate tokens for the bot."""
    email_key = Fernet.generate_key().decode("utf-8")
    token_secret = Fernet.generate_key().decode("utf-8")

    print(
        dedent(
            f"""
    EMAIL_KEY={email_key}
    TOKEN_SECRET={token_secret}
    """
        )
    )


def export_users():
    # exports verified users from the old db to the new db

    import base64
    import json
    import argparse

    import pymysql

    import base64
    import hashlib
    from Crypto import Random
    from Crypto.Cipher import AES

    from luhack_bot.crypto import fernet

    class AESCipher(object):
        """
        A classical AES Cipher. Can use any size of data and any size of password thanks to padding.
        Also ensure the coherence and the type of the data with a unicode to byte converter.
        """

        def __init__(self, key):
            self.bs = 32
            self.key = hashlib.sha256(AESCipher.str_to_bytes(key)).digest()

        @staticmethod
        def str_to_bytes(data):
            u_type = type(b"".decode("utf8"))
            if isinstance(data, u_type):
                return data.encode("utf8")
            return data

        def _pad(self, s):
            return s + (self.bs - len(s) % self.bs) * AESCipher.str_to_bytes(
                chr(self.bs - len(s) % self.bs)
            )

        @staticmethod
        def _unpad(s):
            return s[: -ord(s[len(s) - 1 :])]

        def encrypt(self, raw):
            raw = self._pad(AESCipher.str_to_bytes(raw))
            iv = Random.new().read(AES.block_size)
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            return base64.b64encode(iv + cipher.encrypt(raw)).decode("utf-8")

        def decrypt(self, enc):
            enc = base64.b64decode(enc)
            iv = enc[: AES.block_size]
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            return self._unpad(cipher.decrypt(enc[AES.block_size :])).decode("utf-8")

    parser = argparse.ArgumentParser(description="Export users")
    parser.add_argument("old_aes_key")
    parser.add_argument("old_db_user")
    parser.add_argument("old_db_pass")
    parser.add_argument("old_db_host")
    parser.add_argument("old_db")
    parser.add_argument("old_db_port", type=int)

    def update_user(user, cipher):
        email = user["email"]
        decrypted = cipher.decrypt(email)
        encrypted = base64.b64encode(fernet.encrypt(decrypted.encode("utf-8"))).decode(
            "utf-8"
        )
        user["email"] = encrypted
        return user

    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.old_db_host,
        user=args.old_db_user,
        password=args.old_db_pass,
        port=args.old_db_port,
        db=args.old_db,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    cipher = AESCipher(args.old_aes_key)

    try:
        with conn.cursor() as cursor:
            sql = "SELECT UserID as user_id, Username as username, Email as email from VerifiedUsers, Emails where VerifiedUsers.EmailID = Emails.EmailID"
            cursor.execute(sql)
            users = cursor.fetchall()

        users = [update_user(u, cipher) for u in users]

        print(json.dumps(users))

    finally:
        conn.close()


def ingest_users():
    # ingests users exported from the old db

    import base64
    import json
    import argparse
    import asyncio

    from luhack_bot.crypto import fernet
    from luhack_bot.db.helpers import init_db
    from luhack_bot.db.models import User

    parser = argparse.ArgumentParser(description="Ingest users")
    parser.add_argument("users_file")

    async def insert_users(users):
        await init_db()

        for user in users:
            email = fernet.decrypt(base64.b64decode(user["email"])).decode("utf-8")
            d_id = int(user["user_id"])

            existing_user = await User.get(d_id)
            if existing_user is None:
                await User.create(
                    discord_id=d_id, username=user["username"], email=email
                )
            else:
                await existing_user.update(discord_id=d_id, email=email).apply()

    args = parser.parse_args()

    with open(args.users_file) as f:
        users = json.load(f)

    asyncio.run(insert_users(users))


def export_writeups_and_blog_posts():
    import asyncio
    import json

    from luhack_bot.db.helpers import init_db
    from luhack_bot.db.models import Writeup, Blog

    def id(x):
        return x

    writeup_keys = {"id": id, "author_id": id, "title": id, "slug": id, "tags": id, "content": id, "creation_date": str, "edit_date": str}
    blog_keys = {"id": id, "title": id, "slug": id, "tags": id, "content": id, "creation_date": str, "edit_date": str}

    def t_w(w):
        return {k: f(getattr(w, k)) for k, f in writeup_keys.items()}

    def t_b(b):
        return {k: f(getattr(b, k)) for k, f in blog_keys.items()}

    async def inner():
        await init_db()

        writeups = await Writeup.query.gino.all()
        blogs = await Blog.query.gino.all()

        print(json.dumps([t_w(w) for w in writeups]))
        print(json.dumps([t_b(b) for b in blogs]))

    asyncio.run(inner())
