import logging
import textwrap
from typing import List, Optional

import discord
import sqlalchemy
from sqlalchemy_searchable import search as pg_search
from discord.ext import commands

from luhack_bot.token_tools import generate_writeup_edit_token
from luhack_bot.db.models import User, Writeup, db
from luhack_bot.utils.checks import is_authed
from luhack_bot import constants


logger = logging.getLogger(__name__)


class Writeups(commands.Cog):
    def __init__(self, bot):
        self.luhack_guild = bot.get_guild(constants.luhack_guild_id)

    cog_check = staticmethod(is_authed)

    @staticmethod
    def tag_url(tag):
        return constants.writeups_base_url / "tag" / tag

    @staticmethod
    def writeup_url(slug):
        return constants.writeups_base_url / "writeup" / slug

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

        return f'"{writeup.title}" ({self.writeup_url(writeup.slug)}) by {author}, tags: `{tags}`'

    async def show_similar_writeups(
        self, ctx, title: str, found_message: str = "Possible writeups are:"
    ) -> List[Writeup]:
        """Shows similar writeups to a user."""

        similar = [self.format_writeup(i) for i in await self.search_writeups(title)]

        if similar:
            await ctx.send("{} \n{}\n".format(found_message, "\n".join(similar)))
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

        tags = " ".join("[{}]({})".format(tag, self.tag_url(tag).human_repr()) for tag in writeup.tags)

        embed = discord.Embed(title=writeup.title, timestamp=writeup.creation_date, colour=discord.Colour.blue(), author=self.luhack_guild.get_member(writeup.author_id))
        embed.add_field(name="tags", value=tags, inline=False)
        embed.add_field(name="link", value=self.writeup_url(writeup.slug), inline=False)
        embed.add_field(name="last edited", value=writeup.edit_date, inline=False)

        await ctx.send(embed=embed)

    # @writeups.command(aliases=["create"])
    # async def new(
    #     self,
    #     ctx,
    #     title: commands.clean_content,
    #     tags: commands.clean_content,
    #     *,
    #     content: commands.clean_content,
    # ):
    #     """Create a new writeup."""
    #     await Writeup.create_auto(
    #         author_id=ctx.author.id,
    #         title=title,
    #         tags=tags.split(),
    #         content=content,
    #     )

    #     await ctx.send("Created your writeup.")

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
            await ctx.send("You don't have permission to delete that writeup")
            return

        await writeup.delete()
        await ctx.send(f"RIP {writeup.title}")

    @writeups.command()
    async def token(self, ctx):
        """Generate a token allowing you to create writeups & manage those you have authority to."""

        is_admin = self.luhack_guild.get_member(
            ctx.author.id
        ).guild_permissions.administrator
        token = generate_writeup_edit_token(ctx.author.name, ctx.author.id, is_admin)

        url = constants.writeups_base_url.with_query(token=token)

        await ctx.author.send(f"Visit this link and you'll be authed for 24 hours: {url}")
