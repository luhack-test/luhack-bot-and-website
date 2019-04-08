from starlette.requests import HTTPConnection
from starlette.authentication import AuthenticationBackend, AuthenticationError, BaseUser, AuthCredentials

from luhack_bot.token_tools import decode_writeup_edit_token


class User(BaseUser):
    def __init__(self, discord_id: int, is_admin: bool):
        self.discord_id = discord_id
        self.is_admin = is_admin


class TokenAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: HTTPConnection):
        token = request.query_params.get("token")

        if token is None and "token" in request.session:
            token = request.session["token"]

        decoded = decode_writeup_edit_token(token)
        if decoded is None:
            return

        request.session["token"] = token

        user_id, is_admin = decoded

        creds = ["authenticated"]
        if is_admin:
            creds.append("admin")

        return AuthCredentials(creds), User(user_id, is_admin)
