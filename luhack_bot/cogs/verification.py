import asyncio
import logging

import discord
from discord.ext import commands

from luhack_bot import constants, email_tools, token_tools, secrets
from luhack_bot.db.models import User
from luhack_bot.utils.checks import is_in_luhack, is_disciple_or_admin, in_channel

logger = logging.getLogger(__name__)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)
        self.potential_role = self.luhack_guild.get_role(
            constants.potential_luhacker_role_id
        )
        self.prospective_role = self.luhack_guild.get_role(
            constants.prospective_luhacker_role_id
        )
        self.verified_role = self.luhack_guild.get_role(
            constants.verified_luhacker_role_id
        )

        bot.loop.create_task(self.fix_missing_roles())
        bot.loop.create_task(self.update_usernames())

    def get_member_in_luhack(self, user_id: int) -> discord.Member:
        """Try and fetch a member in the luhack guild."""
        return self.luhack_guild.get_member(user_id)

    def bot_check_once(self, ctx):
        return is_in_luhack(ctx)

    async def apply_roles(self, member):
        user = await User.get(member.id)
        if user is not None:
            await member.add_roles(self.verified_role)
            await member.remove_roles(self.potential_role, self.prospective_role)
        else:
            await member.add_roles(self.potential_role)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # if the user is already in the db, then they're verified
        await self.apply_roles(member)

    async def fix_missing_roles(self):
        """Apply missing roles on bot startup"""
        for member in self.luhack_guild.members:
            await self.apply_roles(member)

    async def update_usernames(self):
        users = await User.query.gino.all()
        for user in users:
            member = self.luhack_guild.get_member(user.discord_id)
            if member is None:
                continue
            await user.update(username=member.name).apply()

    @commands.command()
    async def become_prospective(self, ctx, token: str):
        """Become a prospective luhacker."""
        if token != secrets.prospective_token:
            raise commands.CheckFailure("Not a valid prospective token")

        member = self.get_member_in_luhack(ctx.author.id)

        await member.remove_roles(self.potential_role)
        await member.add_roles(self.prospective_role)
        await ctx.send("Prospective luhacker granted, congrats!")
        await self.bot.log_message(f"made member prospective {member} ({member.id})")

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
        name="verify_token", aliases=["auth_plz", "i_really_wanna_be_wizard"]
    )
    async def verify_token(self, ctx, auth_token: str):
        """Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker.
        Note that tokens expire after 30 minutes.

        Second step on the path to Grand Master Cyber Wizardl.
        """
        existing_user = await User.get(ctx.author.id)
        is_flagged = (
            existing_user is not None and existing_user.flagged_for_deletion is not None
        )

        if existing_user is not None and not is_flagged:
            raise commands.CheckFailure("It seems you've already registered.")

        user = token_tools.decode_auth_token(auth_token)

        if user is None:
            raise commands.CheckFailure(
                "That token is invalid or is older than 30 minutes and expired."
            )

        user_id, user_email = user

        if user_id != ctx.author.id:
            raise commands.CheckFailure(
                "Seems you're not the same person that generated the token, go away."
            )

        member: discord.Member = self.get_member_in_luhack(ctx.author.id)

        assert member is not None

        logger.info("Verifying member: %s", ctx.author)

        if is_flagged:
            await existing_user.update(flagged_for_deletion=None).apply()
            await ctx.send("Congrats, you've been re-verified!")
            await self.bot.log_message(f"re-verified member {member} ({member.id})")
            return

        user = User(discord_id=user_id, username=member.name, email=user_email)
        await user.create()

        await member.remove_roles(self.potential_role, self.prospective_role)
        await member.add_roles(self.verified_role)

        await ctx.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
        await self.bot.log_message(f"verified member {member} ({member.id})")

    @commands.check(is_disciple_or_admin)
    @commands.check(in_channel(constants.inner_magic_circle_id))
    @commands.command()
    async def add_user_manually(self, ctx, member: discord.Member, email: str):
        """Manually auth a member."""
        logger.info("Verifying member: %s", ctx.author)

        user = User(discord_id=member.id, username=member.name, email=email)
        await user.create()

        await member.remove_roles(self.potential_role, self.prospective_role)
        await member.add_roles(self.verified_role)

        await member.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
        await ctx.send(f"Manually verified {member}")
        await self.bot.log_message(f"verified member {member} ({member.id})")

    @commands.check(is_disciple_or_admin)
    @commands.check(in_channel(constants.inner_magic_circle_id))
    @commands.command()
    async def check_email(self, ctx, name: str):
        """See what user an email belongs to."""
        users = await User.query.gino.all()

        for user in users:
            if name in user.email:
                await ctx.send(
                    f"User: {user.username} ({user.discord_id}). Joined at: {user.joined_at}, Last talked: {user.last_talked}"
                )
                return
        else:
            await ctx.send("No user with that email exists.")
