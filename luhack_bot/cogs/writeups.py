import logging
import textwrap
from typing import List, Optional

import discord
import sqlalchemy
from sqlalchemy_searchable import search as pg_search
from discord.ext import commands

from luhack_bot.db.models import User, Writeup, db
from luhack_bot.utils.checks import is_authed
from luhack_bot import constants


logger = logging.getLogger(__name__)


class Writeups(commands.Cog):
    def __init__(self, bot):
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)

    check_once = staticmethod(is_authed)

    async def get_writeup(self, title: str) -> Optional[Writeup]:
        return await Writeup.query.where(Writeup.title == title).gino.first()

    async def search_writeups(self, search: str) -> List[Writeup]:
        """Search for writeups, return top 3 matching."""
        return await pg_search(Writeup.query, search, sort=True).limit(3).gino.all()

    def can_edit_writeup(self, writeup: Writeup, user_id: int) -> bool:
        return (
            writeup.author_id == user_id
            or self.luhack_guild.get_member(user_id).guild_permissions.administrator
        )

    def format_writeup(self, writeup: Writeup) -> str:
        author = self.luhack_guild.get_member(writeup.author_id)
        tags = ", ".join(writeup.tags)

        return f'"{writeup.title}" by "{author}": {tags}'

    async def show_similar_writeups(
        self, ctx, title: str, found_message: str = "Possible writeups are:"
    ) -> List[Writeup]:
        """Shows similar writeups to a user."""

        similar = [self.format_writeup(i) for i in await self.search_writeups(title)]

        if similar:
            await ctx.send("{} ```\n{}\n```".format(found_message, "\n".join(similar)))
        else:
            await ctx.send("No writeups found, sorry.")

    @commands.group(aliases=["writeup"], invoke_without_command=True)
    async def writeups(self, ctx, *, title: str):
        """Retrieve a writeup by name."""

        writeup = await self.get_writeup(title)

        if writeup is None:
            await self.show_similar_writeups(
                ctx, title, "Writeup by that title not found, similar writeups are:"
            )
            return

        await ctx.send(writeup.content)

    @writeups.command(aliases=["create"])
    async def new(
        self,
        ctx,
        title: commands.clean_content,
        tags: commands.clean_content,
        *,
        content: commands.clean_content,
    ):
        """Create a new writeup."""
        await Writeup.create(
            author_id=ctx.author.id, title=title, tags=tags.split(), content=content
        )

        await ctx.send("Created your writeup.")

    @writeups.command()
    async def info(self, ctx, *, title: str):
        """Get info about a writeup."""
        writeup = await self.get_writeup(title)

        if writeup is None:
            await self.show_similar_writeups(
                ctx, title, "Writeup by that title not found, similar writeups are:"
            )
            return

        author = self.luhack_guild.get_member(writeup.author_id)
        tags = ", ".join(writeup.tags)

        await ctx.send(
            f"```\nid: {writeup.id}\nauthor: {author}\ntitle: {writeup.title}\ntags: {tags}\n```"
        )

    @writeups.command()
    async def delete(self, ctx, *, title: str):
        """Delet a writeup"""
        writeup = await self.get_writeup(title)

        if writeup is None:
            await self.show_similar_writeups(
                ctx, title, "Writeup by that title not found, similar writeups are:"
            )
            return

        if not self.can_edit_writeup(writeup, ctx.author.id):
            await ctx.send("You don't have permission to edit that writeup")
            return

        await writeup.delete()
        await ctx.send(f"RIP {writeup.title}")
