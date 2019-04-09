from typing import Optional, Tuple

from itsdangerous import BadSignature, URLSafeTimedSerializer

from luhack_bot.secrets import signing_secret

token_signer = URLSafeTimedSerializer(signing_secret, salt="yeet")


def generate_auth_token(user_id: int, email: str) -> str:
    """Generate an auth token for a user and an email."""
    return token_signer.dumps({"user_id": user_id, "email": email})


def generate_writeup_edit_token(username: str, user_id: int, is_admin: bool) -> str:
    """Generate an auth token for editing/ creating writeups."""
    return token_signer.dumps({"username": username, "user_id": user_id, "is_admin": is_admin})


def decode_auth_token(token: str) -> Optional[Tuple[int, str]]:
    """Decode an auth token, returns either a tuple of the user id and email after decoding a valid token, None otherwise.

    Tokens are valid if they are younger than 30 minutes & we can actually decrypt them.
    """

    try:
        user = token_signer.loads(token, max_age=30 * 60)
        return (user["user_id"], user["email"])
    except BadSignature:
        return None

def decode_writeup_edit_token(token: str) -> Optional[Tuple[str, int, bool]]:
    """Decode a writeup edit token, returns a tuple of the user id and if they are
    admin if the token was valid, None otherwise.

    Writeup edit tokens have a max age of 24h.
    """

    try:
        data = token_signer.loads(token, max_age=24 * 60 * 60)
        return (data["username"], data["user_id"], data["is_admin"])
    except BadSignature:
        return None
