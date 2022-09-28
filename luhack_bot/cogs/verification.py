from __future__ import annotations

import re
import asyncio
import logging
import textwrap
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from luhack_bot import constants
from luhack_bot import email_tools
from luhack_bot import token_tools
from luhack_bot.db.models import User
from luhack_bot.utils.checks import (
    is_admin_int,
    is_in_luhack_int,
)

if TYPE_CHECKING:
    from luhack_bot.bot import LUHackBot

logger = logging.getLogger(__name__)


class CorrectEmailView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = 180):
        self.value: Optional[bool] = None
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        await interaction.edit_original_response(view=None, content="Okay, using the corrected email")
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        await interaction.edit_original_response(view=None, content="Using the email you gave")
        self.stop()


class Verification(commands.GroupCog, name="verify"):
    def __init__(self, bot: LUHackBot):
        self.bot = bot

        asyncio.create_task(self.start_tasks_when_ready())

        #: members that have left the discord but are in the database, we keep
        # track here so we can remove them after they've been away for more than
        # a day
        self.members_flagged_as_left = set()
        super().__init__()

    def get_member_in_luhack(self, user_id: int) -> Optional[discord.Member]:
        """Try and fetch a member in the luhack guild."""
        return self.bot.luhack_guild().get_member(user_id)

    async def interaction_check(self, interaction: discord.Interaction):
        return is_in_luhack_int(interaction)

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

    async def start_tasks_when_ready(self):
        await self.bot.wait_until_ready()
        if not constants.is_test_mode:
            self.fix_missing_roles.start()
            self.update_members.start()

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

    @app_commands.command(
        name="begin",
    )
    @app_commands.describe(
        email="Your lancaster email, in the form `j.doe1@lancs.ac.uk`"
    )
    async def begin_verify(
        self,
        interaction: discord.Interaction,
        *,
        email: app_commands.Transform[str, email_tools.LancsEmailTransformer],
    ):
        """Generates an authentication token, then emails it to the provided email.
        You must provide a valid lancaster email address or you will not get an
        authentication token.

        First step on the path to Grand Master Cyber Wizard

        """

        user, domain = email.split("@")
        await interaction.response.defer(ephemeral=True)

        if not "." in user:
            if (m := re.fullmatch(r"^(\w+?)(\w)(\d*)$", user)) is not None:
                surname, initial, number = m.group(1, 2, 3)
                corrected = f"{initial}.{surname}{number}@{domain}"
                view = CorrectEmailView()
                msg = textwrap.dedent(
                    f"""
                Looks like your email is in the incorrect format, is this your email?
                `{corrected}`
                """
                )
                await interaction.followup.send(content=msg, view=view)
                await view.wait()
                if view.value:
                    email = corrected

        user_id = interaction.user.id
        existing_user = await User.query.where(
            (User.discord_id == user_id) | (User.email == email)
        ).gino.first()

        if existing_user and existing_user.discord_id != user_id:
            await interaction.followup.send(
                "Looks like you're already registered with this email address",
                ephemeral=True,
            )
            return

        if existing_user is not None:
            await interaction.followup.send(
                "It seems you've already registered.", ephemeral=True
            )
            return

        auth_token = token_tools.generate_auth_token(user_id, email)

        logger.info("Generated token for user: %s, %s", interaction.user, auth_token)

        await email_tools.send_verify_email(email, auth_token)

        await interaction.followup.send(
            f"Okay, I've sent an email to: `{email}` with your token!", ephemeral=True
        )

    @app_commands.command(name="complete")
    async def verify_token(self, interaction: discord.Interaction, *, auth_token: str):
        """Takes an authentication token and elevates you to Verified LUHacker.
        Note that tokens expire after 30 minutes.

        Second step on the path to Grand Master Cyber Wizard.
        """
        user_id = interaction.user.id
        existing_user = await User.get(user_id)

        if existing_user is not None:
            raise commands.CheckFailure("It seems you've already registered.")

        user = token_tools.decode_auth_token(auth_token)

        if user is None:
            raise commands.CheckFailure(
                "That token is invalid or is older than 30 minutes and expired."
            )

        user_id, user_email = user

        if user_id != user_id:
            raise commands.CheckFailure(
                "Seems you're not the same person that generated the token, go away."
            )

        member = self.get_member_in_luhack(user_id)

        assert member is not None

        logger.info("Verifying member: %s", interaction.user)

        await interaction.response.send_message(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!",
            ephemeral=True,
        )
        await self.bot.log_message(f"verified member {member} ({member.id})")

        user = await User.create(
            discord_id=user_id, username=member.name, email=user_email
        )

        await member.remove_roles(self.bot.potential_role())
        await member.add_roles(self.bot.verified_role())

        logger.info("Finished verifying member: %s", interaction.user)


@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
class VerificationAdmin(commands.GroupCog, name="verify_admin"):
    def __init__(self, bot: LUHackBot):
        self.bot = bot

        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction):
        return is_admin_int(interaction)

    @app_commands.command(name="verify_manually")
    async def add_user_manually(
        self, interaction: discord.Interaction, *, member: discord.Member, email: str
    ):
        """Manually auth a member."""
        logger.info("Verifying member: %s", member)

        await User.create(discord_id=member.id, username=member.name, email=email)

        await member.remove_roles(self.bot.potential_role())
        await member.add_roles(self.bot.verified_role())

        await member.send(
            "Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!"
        )
        await interaction.response.send_message(f"Manually verified {member}")
        await self.bot.log_message(f"verified member {member} ({member.id})")

    @app_commands.command(name="user_info")
    async def user_info(
        self, interaction: discord.Interaction, *, member: discord.Member
    ):
        """Get info for a user."""
        user = await User.get(member.id)

        if user is None:
            await interaction.response.send_message(
                "No info for that user ;_;", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"User: {user.username} ({user.discord_id}) <{user.email}>. Joined at: {user.joined_at}",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Verification(bot))
    await bot.add_cog(VerificationAdmin(bot))
