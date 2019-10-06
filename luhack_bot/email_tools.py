import logging
import textwrap
from email.mime.text import MIMEText

from discord.ext.commands import BadArgument

import aiosmtplib
from luhack_bot.secrets import email_password
from luhack_bot.secrets import email_username

logger = logging.getLogger(__name__)


async def send_verify_email(target_email: str, token: str):
    """Send an auth email."""
    subject = "LUHack Discord Verification Bot Authentication Email"

    body = textwrap.dedent(
        f"""
        Hello!
        You are receiving this email because you have requested to authenticate yourself as a valid Lancaster University student on the LUHack Discord server.


        Your authentication token is: {token}
        """
    )

    msg = MIMEText(body)
    msg["From"] = email_username
    msg["To"] = target_email
    msg["Subject"] = subject

    async with aiosmtplib.SMTP("smtp.gmail.com", port=465, use_tls=True) as smtp:
        await smtp.login(email_username, email_password)
        await smtp.send_message(msg)

    logger.info(f"Sent auth email to: {target_email}")


async def send_reverify_email(target_email: str):
    """Send an auth email."""
    subject = "LUHack Discord inactivity reminder"

    body = textwrap.dedent(
        f"""
        Heya!
        You are receiving this email because you haven't been active on the luhack discord server for a while.
        To remain in the server you'll need to re-verify using the `!gen_token` command again or you'll be removed in a week.
        """
    )

    msg = MIMEText(body)
    msg["From"] = email_username
    msg["To"] = target_email
    msg["Subject"] = subject

    async with aiosmtplib.SMTP("smtp.gmail.com", port=465, use_tls=True) as smtp:
        await smtp.login(email_username, email_password)
        await smtp.send_message(msg)

    logger.info(f"Sent reverify request email to: {target_email}")


def is_lancs_email(email: str) -> bool:
    """Check if the email is a lancs email address"""
    return email.endswith(("@lancaster.ac.uk", "@lancs.ac.uk", "@live.lancs.ac.uk"))


def lancs_email(email: str) -> str:
    """Command converter that checks the email is a lancaster email."""

    if not is_lancs_email(email):
        raise BadArgument(
            "Invalid email, please provide a valid lancs email, such as @lancaster.ac.uk, @lancs.ac.uk, or @live.lancs.ac.uk"
        )

    return email
