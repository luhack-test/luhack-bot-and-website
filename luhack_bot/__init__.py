import sys
import logging

from textwrap import dedent
from cryptography.fernet import Fernet


def run():
    """Run the bot."""
    from luhack_bot import bot

    ch = logging.StreamHandler(sys.stderr)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    ch.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

    logger.info("Starting up bot")

    bot.start()

    logger.info("Bot shutting down")


def gen_tokens():
    """Generate tokens for the bot."""
    email_key = Fernet.generate_key().decode('utf-8')
    token_secret = Fernet.generate_key().decode('utf-8')

    print(
        dedent(
            f"""
    EMAIL_KEY={email_key}
    TOKEN_SECRET={token_secret}
    """
        )
    )
