from gino import Gino
from luhack_bot.secrets import email_encryption_key
from slug import slug
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types import TSVectorType

db = Gino()

class User(db.Model):
    """Full users, that have a lancs email."""

    __tablename__ = "users"

    discord_id = db.Column(db.BigInteger(), primary_key=True)
    username = db.Column(db.Text(), nullable=False)
    email = db.Column(EncryptedType(db.Text(), email_encryption_key), nullable=False)
    #: when the user became verified, not when they joined the guild
    joined_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    completed_challenges = relationship(
        "Challenge", secondary=lambda: CompletedChallenge, back_populates="challenges"
    )


class Writeup(db.Model):
    __tablename__ = "writeups"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(
        None, db.ForeignKey("users.discord_id", ondelete="SET NULL"), nullable=True
    )
    author = relationship(User, backref=backref("writeups"), lazy="joined")

    title = db.Column(db.Text(), nullable=False, unique=True)

    slug = db.Column(db.Text(), nullable=False, unique=True)
    _slug_nonempty = (db.CheckConstraint('slug!=""'),)

    tags = db.Column(ARRAY(db.Text()), nullable=False)
    content = db.Column(db.Text(), nullable=False)

    creation_date = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    edit_date = db.Column(
        db.DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )

    search_vector = db.Column(
        TSVectorType("title", "content", weights={"title": "A", "content": "B"})
    )

    private = db.Column(db.Boolean, nullable=False, default=False)

    _tags_idx = db.Index("writeups_tags_array_idx", "tags", postgresql_using="gin")

    @classmethod
    def create_auto(cls, *args, **kwargs):
        if "slug" not in kwargs:
            kwargs["slug"] = slug(kwargs["title"])
        return cls.create(*args, **kwargs)

    def update_auto(self, *args, **kwargs):
        if "slug" not in kwargs:
            kwargs["slug"] = slug(kwargs["title"])
        return self.update(*args, **kwargs)


class Image(db.Model):
    __tablename__ = "images"

    id = db.Column(UUID(), primary_key=True, server_default=func.uuid_generate_v4())

    author_id = db.Column(
        None, db.ForeignKey("users.discord_id", ondelete="SET NULL"), nullable=True
    )
    author = relationship(User, backref=backref("images"), lazy="joined")

    filetype = db.Column(db.Text(), nullable=False)
    image = db.Column(db.LargeBinary(), nullable=False)


class Challenge(db.Model):
    __tablename__ = "challenges"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.Text(), unique=True, nullable=False)
    slug = db.Column(db.Text(), nullable=False, unique=True)
    _slug_nonempty = (db.CheckConstraint('slug!=""'),)

    content = db.Column(db.Text(), nullable=False)
    tags = db.Column(ARRAY(db.Text()), nullable=False)

    flag = db.Column(db.Text(), unique=True, nullable=True)
    answer = db.Column(db.Text(), nullable=True)

    _flag_answer_distinct = db.CheckConstraint("(flag IS NULL) != (answer IS NULL)")

    points = db.Column(db.Integer(), nullable=False)

    completed_users = relationship(
        User, secondary=lambda: CompletedChallenge, back_populates="users"
    )

    creation_date = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    search_vector = db.Column(
        TSVectorType("title", "content", weights={"title": "A", "content": "B"})
    )

    hidden = db.Column(db.Boolean, nullable=False, default=False)
    depreciated = db.Column(db.Boolean, nullable=False, default=False)

    _tags_idx = db.Index("challenge_tags_array_idx", "tags", postgresql_using="gin")

    @classmethod
    def create_auto(cls, *args, **kwargs):
        if "slug" not in kwargs:
            kwargs["slug"] = slug(kwargs["title"])
        return cls.create(*args, **kwargs)

    def update_auto(self, *args, **kwargs):
        if "slug" not in kwargs:
            kwargs["slug"] = slug(kwargs["title"])
        return self.update(*args, **kwargs)


class CompletedChallenge(db.Model):
    __tablename__ = "completedchallenges"

    discord_id = db.Column(
        None,
        db.ForeignKey("users.discord_id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    challenge_id = db.Column(
        None,
        db.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    season = db.Column(
        db.Integer(), nullable=False, default=1, server_default="1", primary_key=True
    )

class Machine(db.Model):
    """Target infrastructure machines"""

    __tablename__ = "machines"

    id = db.Column(db.Integer, primary_key=True)

    hostname = db.Column(db.Text(), nullable=False, unique=True)
    description = db.Column(db.Text(), nullable=False)

class MachineDisplay(db.Model):
    """Machine display messages"""

    __tablename__ = "machine_displays"

    discord_message_id = db.Column(db.BigInteger(), primary_key=True)
    machine_hostname = db.Column(db.Text(), nullable=False)
