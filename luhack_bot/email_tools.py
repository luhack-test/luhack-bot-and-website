import logging
import textwrap
from aiosmtplib import SMTP
from email.message import EmailMessage
from discord import app_commands
import discord

from discord.ext.commands import BadArgument

from luhack_bot.constants import from_email_address

logger = logging.getLogger(__name__)


async def send_verify_email(target_email: str, token: str):
    """Send an auth email."""
    subject = "LUHack Discord Verification Bot Authentication Email"

    body = textwrap.dedent(
        f"""
        Hello!
        You are receiving this email because you have requested to authenticate yourself as a valid Lancaster University student on the LUHack Discord server.


        Your authentication token is: {token}

        DM the bot and use the command: "/verify complete auth_token:{token}"
        """
    )

    message = EmailMessage()
    message["From"] = from_email_address
    message["To"] = target_email
    message["Subject"] = subject
    message.set_content(body)

    smtp_client = SMTP(hostname="smtp.lancs.ac.uk")
    async with smtp_client:
        await smtp_client.send_message(message)

    logger.info(f"Sent auth email to: {target_email}")


async def send_reverify_email(target_email: str):
    """Send an auth email."""
    subject = "LUHack Discord inactivity reminder"

    body = textwrap.dedent(
        f"""
        Heya!
        You are receiving this email because you haven't been active on the luhack discord server for a while.
        To remain in the server you'll need to re-verify using the `!token` command again or you'll be removed in a week.
        """
    )

    message = EmailMessage()
    message["From"] = from_email_address
    message["To"] = target_email
    message["Subject"] = subject
    message.set_content(body)

    smtp_client = SMTP(hostname="smtp.lancs.ac.uk")
    async with smtp_client:
        await smtp_client.send_message(message)

    logger.info(f"Sent reverify request email to: {target_email}")


def is_lancs_email(email: str) -> bool:
    """Check if the email is a lancs email address"""
    return email.endswith(("@lancaster.ac.uk", "@lancs.ac.uk", "@live.lancs.ac.uk"))


class LancsEmailTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> str:
        if not is_lancs_email(value):
            raise BadArgument(
                "Invalid email, please provide a valid lancs email, such as @lancaster.ac.uk, @lancs.ac.uk, or @live.lancs.ac.uk"
            )

        return value
