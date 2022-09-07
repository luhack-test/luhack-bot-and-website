import logging
import time
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from luhack_bot import constants
from luhack_bot.db.helpers import init_db
from luhack_bot.secrets import bot_client_token

logger = logging.getLogger(__name__)


COGS = [
    "cogs.admin",
    "cogs.verification",
    "cogs.writeups",
    "cogs.challenges",
    "cogs.notifier",
]


class LUHackBot(commands.Bot):
    def __init__(self, **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        base_kwargs = {
            "command_prefix": ["L!", "!"],
            "pm_help": True,
            "intents": intents,
        }
        base_kwargs.update(kwargs)
        super().__init__(**base_kwargs)

    async def on_ready(self):
        await self.change_presence(
            activity=discord.Game(name="Hack The IoT Space Bulb")
        )
        print("-----------Bot Credentials-----------")
        print(f"Name:       {self.user.name}")
        print(f"User ID:    {self.user.id}")
        print(f'Timestamp:  {time.strftime("%Y-%m-%d %H:%M:%S")}')
        print("----------------Logs-----------------")

    async def load_cogs(self):
        """Register our cogs."""
        for extension in COGS:
            try:
                await self.load_extension("luhack_bot." + extension)
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")

    async def setup_hook(self):
        await init_db()
        await self.load_cogs()

        if os.getenv("GUILDIFY_COMMANDS") is not None:
            self.tree.copy_global_to(guild=discord.Object(constants.luhack_guild_id))

        original_on_error = self.tree.on_error

        async def outer_error(*args, **kwargs):
            await self.on_interaction_error(*args, **kwargs)
            await original_on_error(*args, **kwargs)

        self.tree.on_error = outer_error

        if os.getenv("SYNC_COMMANDS") is not None:
            logger.info("Syncing commands")
            await self.tree.sync()
            await self.tree.sync(guild=discord.Object(constants.luhack_guild_id))

    def luhack_guild(self) -> discord.Guild:
        guild = self.get_guild(constants.luhack_guild_id)
        assert guild is not None
        return guild

    def potential_role(self):
        return self.luhack_guild().get_role(constants.potential_luhacker_role_id)

    def prospective_role(self):
        return self.luhack_guild().get_role(constants.prospective_luhacker_role_id)

    def verified_role(self):
        return self.luhack_guild().get_role(constants.verified_luhacker_role_id)

    async def log_message(self, *args, **kwargs):
        luhack_guild = self.luhack_guild()
        log_chan = luhack_guild.get_channel(constants.bot_log_channel_id)

        if log_chan is None:
            logger.warn("Log channel is missing")
            return

        assert isinstance(log_chan, discord.TextChannel)

        await log_chan.send(*args, **kwargs)

    async def on_interaction_error(self, interaction: discord.Interaction, error: Optional[BaseException]):
        if isinstance(error, app_commands.TransformerError):
            error = error.__cause__
        if isinstance(error, (commands.BadArgument, commands.CheckFailure, commands.CommandOnCooldown)):
            await interaction.response.send_message(str(error), ephemeral=True)

    async def on_command_error(self, ctx, error):
        # when a command was called invalidly, give info
        if ctx.command is not None:
            assert self.help_command is not None
            cmd = self.help_command.copy()
            cmd.context = ctx
            await cmd.prepare_help_command(ctx, ctx.command.qualified_name)
            prepared_help = cmd.get_command_signature(ctx.command)

            if isinstance(error, commands.NoPrivateMessage):
                await ctx.send("This command cannot be used in private messages")
                return

            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(
                    f"Command missing required argument: {error}\nUsage: `{prepared_help}`"
                )
                return

            elif isinstance(error, commands.BadArgument):
                await ctx.send(f"{error}\nUsage: `{prepared_help}`")
                return

            elif isinstance(error, (commands.CommandOnCooldown, commands.CheckFailure)):
                await ctx.send(error)
                return

        elif isinstance(error, commands.CommandNotFound):
            return

        await ctx.send("Something's borked, sorry")
        await self.log_message(f"An error happened: {error}")
        logger.error(
            "oof: %s", error, exc_info=(type(error), error, error.__traceback__)
        )


def start():
    bot = LUHackBot()
    bot.run(bot_client_token)
