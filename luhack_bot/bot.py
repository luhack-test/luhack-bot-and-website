# Created by DethMetalDuck
# LUHack_Discord_Verification_Bot contains the main logic for the bot
import asyncio
import logging
import time

import discord
from discord.ext import commands

from luhack_bot.db.helpers import init_db
from luhack_bot.secrets import bot_client_token
from luhack_bot.cogs import verification


logger = logging.getLogger(__name__)

***REMOVED***
***REMOVED***
***REMOVED***


class LUHackBot(commands.Bot):
    def __init__(self, **kwargs):
        base_kwargs = {"command_prefix": "L!", "pm_help": True}
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

        self.load_cogs()

    def load_cogs(self):
        """Register our cogs."""
        self.add_cog(verification.Verification(self))

    async def on_command_error(self, ctx, error):
        # when a command was called invalidly, give info
        if ctx.command is not None:
            prepared_help = "{0.prefix}{1.signature}".format(ctx, ctx.command)

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(
                "This command cannot be used in private messages", delete_after=5
            )
            return

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Command missing required argument: {error}\nUsage: `{prepared_help}`",
                delete_after=10,
            )
            return

        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{error}\nUsage: `{prepared_help}`", delete_after=10)
            return

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(error, delete_after=5)
            return

        elif isinstance(error, commands.CheckFailure):
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
