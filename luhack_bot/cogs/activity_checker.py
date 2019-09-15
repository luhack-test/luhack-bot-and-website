import textwrap
import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from luhack_bot import constants
from luhack_bot.utils.checks import is_admin_in_guild
from luhack_bot.db.models import User

logger = logging.getLogger(__name__)


class ActivityChecker(commands.Cog):
    """Cog for keeping track of when members last spoke, if they've not spoken in a
    month: we'll ask them to re-verify, then remove the verified role after a
    week or so.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)
        self.task = asyncio.create_task(self.background_loop())

    async def cog_check(self, ctx):
        return is_admin_in_guild(ctx)

    def get_member_in_luhack(self, user_id: int) -> discord.Member:
        """Try and fetch a member in the luhack guild."""
        return self.luhack_guild.get_member(user_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        user = await User.get(message.author.id)
        if user is None:
            return

        await user.update(last_talked=datetime.utcnow()).apply()

    async def remove_verified_user(self, user: User):
        member = self.get_member_in_luhack(user.discord_id)

        if member is None:
            return

        await member.send(
            "Hey, you've been inactive on luhack for a long time so we've removed you from the guild and unverified you, feel free to join back and re-verify."
        )

        await self.bot.log_message(
            f"Removed member {member} ({member.id}) for being flagged for more than a week."
        )

        await user.delete()

        await member.kick(reason="Removed for being inactive.")

    def get_inactive_potential_members(self):
        """Is the member potential only and joined more than a month ago?"""
        one_month_ago = datetime.utcnow() - timedelta(weeks=4)

        def check(member: discord.Member):
            # role ids of all member roles except @everyone
            role_ids = [r.id for r in member.roles if not r.is_default()]

            # potential users are any users with no roles, or only role is the potential role
            # so if they have anything else, we don't get them here
            if role_ids and role_ids != [constants.potential_luhacker_role_id]:
                return False

            return member.joined_at < one_month_ago

        return [m for m in self.luhack_guild.members if check(m)]

    async def get_inactive_verified_members(self):
        """Get verified but inactive members"""
        one_month_ago = datetime.utcnow() - timedelta(weeks=4)

        async def check(member: discord.Member):
            # role ids of all member roles except @everyone
            user = await User.get(member.id)
            if user is None:
                return False

            if self.is_member_excepted(member):
                return False

            return user.last_talked < one_month_ago

        return [m for m in self.luhack_guild.members if await check(m)]

    def is_member_excepted(self, member: discord.Member) -> bool:
        """Is the member disciple?"""
        role_ids = {role.id for role in member.roles}
        return bool(role_ids & constants.trusted_role_ids)

    async def flag_inactive_member(self, member: discord.Member):
        user = await User.get(member.id)
        if user is None:
            return

        await member.send("Hey, you've been inactive on luhack for a while, to remain in the server you'll "
                          "need to re-verify using `!gen_token` again or you will be removed in a week.")
        await user.update(flagged_for_deletion=datetime.utcnow()).apply()

    async def background_loop(self):
        """The background task for fetching users that haven't messaged in a month."""
        while True:
            logger.info("Running pass of removing flagged users")
            one_week_ago = datetime.utcnow() - timedelta(weeks=1)

            users_to_delete = await User.query.where(
                (User.flagged_for_deletion != None)
                & (User.flagged_for_deletion < one_week_ago)
            ).gino.all()

            logger.info(f"Users to remove: {users_to_delete}")

            for user in users_to_delete:
                await self.remove_verified_user(user)

            for member in self.get_inactive_potential_members():
                await self.bot.log_message(
                    f"Kicking inactive potential-only member {member} ({member.id})"
                )
                await member.kick(reason="Inactive potential-only user.")

            await asyncio.sleep(timedelta(days=1).total_seconds())

    @commands.command()
    async def manually_flag_inactive(self, ctx, member: discord.Member):
        await self.flag_inactive_member(member)

    @commands.command(name="mark_inactive")
    async def mark_inactive_dry(self, ctx):
        """Mark inactive users, this is a dry run."""
        inactive = await self.get_inactive_verified_members()

        total_members = len(self.luhack_guild.members)

        stats = f"{100 * len(inactive) / total_members:.0f}% (inactive: {len(inactive)} / total: {total_members})"

        paginator = commands.Paginator(prefix="", suffix="")

        paginator.add_line(f"Flagged users ({stats}) (dry run):")

        for m in inactive:
            paginator.add_line(f"{m.mention} ({m.id})")

        for page in paginator.pages:
            await ctx.send(page)

    @commands.command(name="mark_inactive_non_dry")
    async def mark_inactive(self, ctx):
        """Mark inactive users."""
        inactive = await self.get_inactive_verified_members()

        total_members = len(self.luhack_guild.members)

        stats = f"{100 * len(inactive) / total_members:.0f}% (inactive: {len(inactive)} / total: {total_members})"

        paginator = commands.Paginator(prefix="", suffix="")

        paginator.add_line(f"Flagged users ({stats}):")

        for m in inactive:
            paginator.add_line(f"{m.mention} ({m.id})")

        for page in paginator.pages:
            await ctx.send(page)

        for member in inactive:
            await self.flag_inactive_member(member)
