import logging

import discord
from discord.ext import commands

from luhack_bot import constants, email_tools, token_tools
from luhack_bot.db.models import User
from luhack_bot.utils.checks import is_in_luhack

logger = logging.getLogger(__name__)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)
        self.potential_role = self.luhack_guild.get_role(
            constants.potential_luhacker_role_id
        )
        self.verified_role = self.luhack_guild.get_role(
            constants.verified_luhacker_role_id
        )

    def get_member_in_luhack(self, user_id: int) -> discord.Member:
        """Try and fetch a member in the luhack guild."""
        return self.luhack_guild.get_member(user_id)

    bot_check_once = staticmethod(is_in_luhack)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # if the user is already in the db, then they're verified
        user = await User.get(member.id)
        if user is not None:
            await member.add_roles(
                self.verified_role, reason="Verified member re-joined"
            )
        else:
            await member.add_roles(self.potential_role, reason="Member joined")

    @commands.command(
        name="gen_token",
        aliases=["gib_token", "i_wanna_be_wizard_too", "generate_token"],
    )
    async def generate_token(self, ctx, email: email_tools.lancs_email):
        """Generates an authentication token, then emails it to the provided email if
        you aren't already verified. You must provide a valid lancaster email address or
        you will not get an authentication token.

        First step on the path to Grand Master Cyber Wizard
        """
        if (await User.get(ctx.author.id)) is not None:
            raise commands.CheckFailure("It seems you've already registered.")

        auth_token = token_tools.generate_auth_token(ctx.author.id, email)

        logger.info("Generated token for user: %s, %s", ctx.author, auth_token)

        await email_tools.send_email(email, auth_token)

        await ctx.send(f"Noice, I've sent an email to: `{email}` with your token!")

    @commands.command(
        name="verify_token",
        aliases=["auth_plz", "i_really_wanna_be_wizard"],
    )
    async def verify_token(self, ctx, auth_token: str):
        """Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker.
        Note that tokens expire after 30 minutes.

        Second step on the path to Grand Master Cyber Wizardl.
        """
        if (await User.get(ctx.author.id)) is not None:
            raise commands.CheckFailure("It seems you've already registered.")

        user = token_tools.decode_token(auth_token)

        if user is None:
            raise commands.CheckFailure(
                "That token is invalid or is older than 30 minutes and expired."
            )

        member = self.get_member_in_luhack(ctx.author.id)

        assert member is not None

        logger.info("Verifying member: %s", ctx.author)

        await user.create()

        await member.remove_roles(self.potential_role)
        await member.add_roles(self.verified_role)

        await ctx.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
