from gino import Gino
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine

from luhack_bot.secrets import email_encryption_key

db = Gino()


class User(db.Model):
    __tablename__ = "users"

    discord_id = db.Column(db.BigInteger(), primary_key=True)
    email = db.Column(EncryptedType(db.Unicode(), email_encryption_key), nullable=False)
