import textwrap
import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from luhack_bot import constants
from luhack_bot.utils.checks import is_disciple_or_admin
from luhack_bot.db.models import User

logger = logging.getLogger(__name__)


class ActivityChecker(commands.Cog):
    """Cog for keeping track of when members last spoke, if they've not spoken in a
    year: we'll ask them to re-verify, then remove the verified role after a
    week or so.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)
        self.task = asyncio.create_task(self.background_loop())

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
        # await user.delete()
        member = self.get_member_in_luhack(user.discord_id)

        if member is None:
            return

        # await member.send(
        #     textwrap.dedent(
        #         """
        # Hey, you've been inactive on luhack for a long time so we've removed you from
        # the guild and unverified you, feel free to join back and re-verify.
        # """
        #     )
        # )

        await self.bot.log(
            f"Removed member {member} ({member.id}) for being flagged for more than a week."
        )

        # await member.kick(reason="Removed for being inactive.")

    def get_inactive_potential_members(self):
        """Is the member potential only and joined more than a month ago?"""
        one_month_ago = datetime.utcnow() - timedelta(weeks=4)

        def check(member: discord.Member):
            # role ids of all member roles except @everyone
            role_ids = [r.id for id in member.roles[1:]]

            # no roles, or only role is the potential role
            if role_ids and role_ids != [constants.potential_luhacker_role_id]:
                return False

            return member.joined_at < one_month_ago

        return [m for m in self.luhack_guild.members if check(m)]

    async def get_inactive_verified_members(self):
        """Get verified but inactive members"""
        three_month_ago = datetime.utcnow() - timedelta(weeks=3 * 4)

        async def check(member: discord.Member):
            # role ids of all member roles except @everyone
            user = await User.get(member.id)
            if user is None:
                return False

            if self.is_member_excepted(member):
                return False

            return user.last_talked < three_month_ago

        return [m for m in self.luhack_guild.members if await check(m)]

    def is_member_excepted(self, member: discord.Member):
        """Does the member have a role other than potential or verified?"""
        for role in member.roles[1:]:
            if role.id not in (
                constants.potential_luhacker_role_id,
                constants.verified_luhacker_role_id,
            ):
                return True
        return False

    async def flag_inactive_member(self, member: discord.Member):
        user = await User.get(member.id)
        if user is None:
            return

        # await member.send("Hey, you've been inactive on luhack for a while, to remain in the server you'll "
        #                   "need to re-verify using `!gen_token` again or you will be removed in a week.")
        await user.update(flagged_for_deletion=datetime.utcnow()).apply()

    async def background_loop(self):
        """The background task for fetching users that haven't messaged in a year."""
        while True:
            await asyncio.sleep(timedelta(days=1).total_seconds())

            one_week_ago = datetime.utcnow() - timedelta(weeks=1)

            users_to_delete = await User.query.where(
                (User.flagged_for_deletion != None)
                & (User.flagged_for_deletion < one_week_ago)
            ).gino.all()
            for user in users_to_delete:
                await self.remove_verified_user(user)

            for member in self.get_inactive_potential_members():
                await self.bot.log(
                    f"Kicking inactive potential-only member {member} ({member.id})"
                )
                # await member.kick(reason="Inactive potential-only user.")

    async def cog_check(self, ctx):
        return is_disciple_or_admin(ctx)

    @commands.command(name="mark_inactive")
    async def mark_inactive_dry(self, ctx):
        """Mark inactive users, this is a dry run."""
        inactive = await self.get_inactive_verified_members()

        await ctx.send("Flagged users (dry run): ```\n" + "\n".join(f"{{m}} ({m.id})" for m in inactive) + "\n```")

    @commands.command(name="mark_inactive_non_dry")
    async def mark_inactive(self, ctx):
        """Mark inactive users."""
        inactive = await self.get_inactive_verified_members()

        await ctx.send("Flagged users: ```\n" + "\n".join(f"{{m}} ({m.id})" for m in inactive) + "\n```")

        for member in inactive:
            await self.flag_inactive_member(member)
