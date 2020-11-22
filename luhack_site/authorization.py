from functools import wraps
from starlette.requests import HTTPConnection
from starlette.authentication import (
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    AuthCredentials,
    UnauthenticatedUser,
)

from luhack_bot.db.models import User as DBUser


class User(SimpleUser):
    is_authed = True

    def __init__(self, username: str, discord_id: int, is_admin: bool):
        super().__init__(username)
        self.discord_id = discord_id
        self.is_admin = is_admin


class LUnauthenticatedUser(UnauthenticatedUser):
    is_authed = False
    is_admin = False


def wrap_result_auth(f):
    @wraps(f)
    async def inner(*args, **kwargs):
        r = await f(*args, **kwargs)
        if r is None:
            return AuthCredentials(), LUnauthenticatedUser()
        return r

    return inner


class TokenAuthBackend(AuthenticationBackend):
    @wrap_result_auth
    async def authenticate(self, request: HTTPConnection):
        if "discord_id" not in request.session:
            request.session.pop("user", None)
            return

        user = request.session.get("user")
        if not user:
            db_user = await DBUser.get(request.session["discord_id"])
            if db_user is None:
                request.session.pop("discord_id", None)
                return
            user = {
                "discord_id": db_user.discord_id,
                "is_admin": db_user.is_admin,
                "username": db_user.username,
            }
            request.session["user"] = user

        username, discord_id, is_admin = (
            user["username"],
            user["discord_id"],
            user["is_admin"],
        )

        creds = ["authenticated"]
        if is_admin:
            creds.append("admin")

        return AuthCredentials(creds), User(username, discord_id, is_admin)


def can_edit(request, author_id=None):
    if not request.user.is_authenticated:
        return False

    if author_id is None:
        return request.user.is_admin

    return request.user.is_admin or author_id == request.user.discord_id
