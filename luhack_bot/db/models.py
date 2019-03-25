from gino import Gino
from sqlalchemy_utils import EncryptedType
from sqlalchemy_searchable import make_searchable
from sqlalchemy_utils.types import TSVectorType

from luhack_bot.secrets import email_encryption_key

db = Gino()


class User(db.Model):
    __tablename__ = "users"

    discord_id = db.Column(db.BigInteger(), primary_key=True)
    email = db.Column(EncryptedType(db.Text(), email_encryption_key), nullable=False)


class Writeup(db.Model):
    __tablename__ = "writeups"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(None, db.ForeignKey("users.discord_id"), nullable=False)

    title = db.Column(db.Text(), nullable=False)
    tags = db.Column(db.ARRAY(db.Text()), nullable=False)
    content = db.Column(db.Text(), nullable=False)

    search_vector = db.Column(
        TSVectorType("title", "content", weights={"title": "A", "content": "B"})
    )

    _tags_idx = db.Index("writeups_tags_array_idx", "tags", postgresql_using="gin")
