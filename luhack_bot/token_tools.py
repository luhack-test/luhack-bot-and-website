from typing import Optional, Tuple

from itsdangerous import BadSignature, URLSafeTimedSerializer

from luhack_bot.secrets import signing_secret

token_signer = URLSafeTimedSerializer(signing_secret, salt="yeet")


def generate_auth_token(user_id: int, email: str) -> str:
    """Generate an auth token for a user and an email."""
    return token_signer.dumps({"user_id": user_id, "email": email})


def decode_token(token: str) -> Optional[Tuple[int, str]]:
    """Decode a token, returns either a tuple of the user id and email after decoding a valid token, None otherwise.

    Tokens are valid if they are younger than 30 minutes & we can actually decrypt them.
    """
    try:
        user = token_signer.loads(token, max_age=30 * 60)
        return (user["user_id"], user["email"])
    except BadSignature:
        return None
