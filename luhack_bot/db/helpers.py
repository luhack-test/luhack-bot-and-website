import os
from typing import Optional

from luhack_bot.db.models import User, db
from luhack_bot.secrets import db_url


async def init_db():
    await db.set_bind(db_url)
    await db.gino.create_all()
