import logging

import discord
from discord.ext import commands
from discord.ext import tasks

from luhack_bot import constants
from luhack_bot import email_tools
from luhack_bot import secrets
from luhack_bot import token_tools
from luhack_bot.db.models import User
from luhack_bot.utils.checks import in_channel
from luhack_bot.utils.checks import is_admin
from luhack_bot.utils.checks import is_in_luhack

logger = logging.getLogger(__name__)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if not constants.is_test_mode:
            self.fix_missing_roles.start()
            self.update_members.start()

        #: members that have left the discord but are in the database, we keep
        # track here so we can remove them after they've been away for more than
        # a day
        self.members_flagged_as_left = set()

    def get_member_in_luhack(self, user_id: int) -> discord.Member:
        """Try and fetch a member in the luhack guild."""
        return self.bot.luhack_guild().get_member(user_id)

    def bot_check_once(self, ctx):
        return is_in_luhack(ctx)

    async def apply_roles(self, member: discord.Member):
        user = await User.get(member.id)
        if user is not None:
            await member.add_roles(self.bot.verified_role())
            await member.remove_roles(
                self.bot.potential_role(), self.bot.prospective_role()
            )
        else:
            await member.add_roles(self.bot.potential_role())

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # if the user is already in the db, then they're verified
        await self.apply_roles(member)

    @tasks.loop(hours=1)
    async def fix_missing_roles(self):
        """Apply missing roles."""
        for member in self.bot.luhack_guild().members:
            try:
                await self.apply_roles(member)
            except discord.errors.NotFound:
                continue

    @tasks.loop(hours=24)
    async def update_members(self):
        users = await User.query.gino.all()
        for user in users:
            member = self.bot.luhack_guild().get_member(user.discord_id)
            if member is None:
                if user.discord_id in self.members_flagged_as_left:
                    await user.delete()
                    self.members_flagged_as_left.discard(user.discord_id)
                else:
                    self.members_flagged_as_left.add(user.discord_id)
            else:
                is_disciple = (
                    discord.utils.get(member.roles, id=constants.disciple_role_id)
                    is not None
                )
                is_admin = member.guild_permissions.administrator or is_disciple

                await user.update(username=member.name, is_admin=is_admin).apply()

    @commands.command()
    async def become_prospective(self, ctx, token: str):
        """Become a prospective luhacker."""
        if token != secrets.prospective_token:
            raise commands.CheckFailure("Not a valid prospective token")

        member = self.get_member_in_luhack(ctx.author.id)

        await member.remove_roles(self.bot.potential_role())
        await member.add_roles(self.bot.prospective_role())
        await ctx.send("Prospective luhacker granted, congrats!")
        await self.bot.log_message(f"made member prospective {member} ({member.id})")

    @commands.command(
        name="token",
        aliases=["gib_token", "i_wanna_be_wizard_too", "generate_token", "gen_token"],
    )
    async def generate_token(self, ctx, email: email_tools.lancs_email):
        """Generates an authentication token, then emails it to the provided email.
        You must provide a valid lancaster email address or you will not get an
        authentication token.

        First step on the path to Grand Master Cyber Wizard

        """
        existing_user = await User.query.where((User.discord_id == ctx.author.id) | (User.email == email)).gino.first()

        if existing_user and existing_user.discord_id != ctx.author.id:
            await ctx.send("Looks like you're already registered with this email address")
            return

        is_flagged = (
            existing_user is not None and existing_user.flagged_for_deletion is not None
        )

        if existing_user is not None and not is_flagged:
            raise commands.CheckFailure("It seems you've already registered.")

        auth_token = token_tools.generate_auth_token(ctx.author.id, email)

        logger.info("Generated token for user: %s, %s", ctx.author, auth_token)

        await email_tools.send_verify_email(email, auth_token)

        await ctx.send(f"Okay, I've sent an email to: `{email}` with your token!")

    @commands.command(
        name="verify", aliases=["auth_plz", "i_really_wanna_be_wizard", "verify_token"]
    )
    async def verify_token(self, ctx, auth_token: str):
        """Takes an authentication token and elevates you to Verified LUHacker.
        Note that tokens expire after 30 minutes.

        Second step on the path to Grand Master Cyber Wizard.
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

        await member.remove_roles(
            self.bot.potential_role(), self.bot.prospective_role()
        )
        await member.add_roles(self.bot.verified_role())

        await ctx.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
        await self.bot.log_message(f"verified member {member} ({member.id})")

    @commands.check(is_admin)
    @commands.command()
    async def add_user_manually(self, ctx, member: discord.Member, email: str):
        """Manually auth a member."""
        logger.info("Verifying member: %s", member)

        user = User(discord_id=member.id, username=member.name, email=email)
        await user.create()

        await member.remove_roles(
            self.bot.potential_role(), self.bot.prospective_role()
        )
        await member.add_roles(self.bot.verified_role())

        await member.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
        await ctx.send(f"Manually verified {member}")
        await self.bot.log_message(f"verified member {member} ({member.id})")

    @commands.check(is_admin)
    @commands.check(in_channel(constants.inner_magic_circle_id))
    @commands.command()
    async def user_info(self, ctx, member: discord.Member):
        """Get info for a user."""
        user = await User.get(member.id)

        if user is None:
            await ctx.send("No info for that user ;_;")
            return

        await ctx.send(
            f"User: {user.username} ({user.discord_id}) <{user.email}>. Joined at: {user.joined_at}, Last talked: {user.last_talked}"
        )

    @commands.check(is_admin)
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
                break
        else:
            await ctx.send("No user with that email exists.")

def setup(bot):
    bot.add_cog(Verification(bot))
