from datetime import datetime
import asyncio

import discord
from discord.ext import commands
import orjson

from luhack_bot import constants
from luhack_bot.cogs.challenges import Challenges
from luhack_bot.db.models import db, Challenge, db


class Notifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        asyncio.create_task(self.setup())

    async def setup(self):
        self.conn = await db.acquire()
        self.raw_conn = await self.conn.get_raw_connection()
        await self.raw_conn.add_listener("bot_notification", self.handle_message)

    def handle_message(self, conn, pid, chan, msg):
        msg = orjson.loads(msg)

        coro = {"challenge_complete": self.handle_challenge_complete}[msg["type"]](msg)

        asyncio.create_task(coro)

    async def handle_challenge_complete(self, msg):
        luhack = self.bot.luhack_guild()
        member = luhack.get_member(msg["discord_id"])
        challenge = await Challenge.get(msg["challenge_id"])

        embed = discord.Embed(
            title=f"Challenge Solved!",
            description=f"{member.mention} just solved '{challenge.title}' and was awarded {challenge.points} points.",
            color=discord.Colour.dark_teal(),
            timestamp=datetime.utcnow(),
            url=str(Challenges.challenge_url(challenge.slug)),
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.avatar_url_as(format="png"),
        )
        channel = luhack.get_channel(constants.challenge_log_channel_id)
        if channel is not None:
            await channel.send(embed=embed)

    async def bye(self):
        if self.conn is None:
            return

        await self.raw_conn.remove_listener("bot_notification", self.handle_message)
        await self.conn.release()

    def cog_unload(self):
        asyncio.create_task(self.bye())


def setup(bot):
    bot.add_cog(Notifier(bot))
