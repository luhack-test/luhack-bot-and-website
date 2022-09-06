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


def export_writeups():
    import asyncio
    import json

    from luhack_bot.db.helpers import init_db
    from luhack_bot.db.models import Writeup

    def id(x):
        return x

    writeup_keys = {"id": id, "author_id": id, "title": id, "slug": id, "tags": id, "content": id, "creation_date": str, "edit_date": str}

    def t_w(w):
        return {k: f(getattr(w, k)) for k, f in writeup_keys.items()}

    async def inner():
        await init_db()

        writeups = await Writeup.query.gino.all()

        print(json.dumps([t_w(w) for w in writeups]))

    asyncio.run(inner())
