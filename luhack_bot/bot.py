# Created by DethMetalDuck
# LUHack_Discord_Verification_Bot contains the main logic for the bot
import asyncio
import logging
import time

import discord
from discord.ext import commands

from luhack_bot import constants
from luhack_bot.db.helpers import init_db
from luhack_bot.secrets import bot_client_token
from luhack_bot.cogs import verification, writeups, activity_checker, todos, admin


logger = logging.getLogger(__name__)


class LUHackBot(commands.Bot):
    def __init__(self, **kwargs):
        base_kwargs = {"command_prefix": ["L!", "!"], "pm_help": True}
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

    def run(self, *args, **kwargs):
        self.loop.create_task(self.load_cogs())
        super().run(*args, **kwargs)

    async def load_cogs(self):
        """Register our cogs."""
        await self.wait_until_ready()
        self.add_cog(verification.Verification(self))
        self.add_cog(writeups.Writeups(self))
        self.add_cog(activity_checker.ActivityChecker(self))
        self.add_cog(todos.Todos(self))
        self.add_cog(admin.Admin(self))

    async def log_message(self, *args, **kwargs):
        luhack_guild = self.get_guild(constants.luhack_guild_id)
        log_chan = luhack_guild.get_channel(constants.bot_log_channel_id)

        if log_chan is None:
            logger.warn("Log channel is missing")
            return

        await log_chan.send(*args, **kwargs)

    async def on_command_error(self, ctx, error):
        # when a command was called invalidly, give info
        if ctx.command is not None:
            cmd = self.help_command.copy()
            cmd.context = ctx
            await cmd.prepare_help_command(ctx, ctx.command.qualified_name)
            prepared_help = cmd.get_command_signature(ctx.command)

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(
                "This command cannot be used in private messages"
            )
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
        logger.error(
            "oof: %s", error, exc_info=(type(error), error, error.__traceback__)
        )


def start():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())

    bot = LUHackBot()
    bot.run(bot_client_token)
