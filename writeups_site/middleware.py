from starlette.requests import HTTPConnection
from starlette.authentication import (
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    AuthCredentials,
)

from luhack_bot.token_tools import decode_writeup_edit_token


class User(SimpleUser):
    def __init__(self, username: str, discord_id: int, is_admin: bool):
        super().__init__(username)
        self.discord_id = discord_id
        self.is_admin = is_admin


class TokenAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: HTTPConnection):
        token = request.query_params.get("token")

        if token is None:
            if "token" not in request.session:
                return
            token = request.session["token"]

        decoded = decode_writeup_edit_token(token)
        if decoded is None:
            return

        request.session["token"] = token

        username, user_id, is_admin = decoded

        creds = ["authenticated"]
        if is_admin:
            creds.append("admin")

        return AuthCredentials(creds), User(username, user_id, is_admin)
