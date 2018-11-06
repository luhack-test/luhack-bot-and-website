# Created by DethMetalDuck
# Token_Handler deals with the generation and verification of tokens for the bot

from itsdangerous import TimestampSigner

from luhack_bot import database_handler
from luhack_bot.secrets import signing_secret

token_signer = TimestampSigner(signing_secret)


# Function that generates a 12 character authentication token, then hashes it and returns that hash
def generate_authentication_token(user_id):
    return token_signer.sign(str(user_id)).decode("utf-8")


# Function that takes a token and then returns the requestid for that token. Should only be called when token is valid
def get_request_id(token):
    # Send a query to the database to get the request id
    sql = "SELECT RequestID FROM Tokens WHERE Token = %s"
    params = (token,)
    resp = database_handler.send_select_query(sql, params)
    if not resp:
        return None

    [(request_id,)] = resp
    return request_id


# Function that takes a given token and checks if it is valid and from the person who asked for it
def validate_token(token):
    _30_minutes = 30 * 60
    return token_signer.validate(token, max_age=_30_minutes)
