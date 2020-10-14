from starlette.config import Config
from starlette.datastructures import Secret


config = Config()

TOKEN_SECRET = config("TOKEN_SECRET", cast=Secret)
LOG_WEBHOOK = config("LOG_WEBHOOK")
