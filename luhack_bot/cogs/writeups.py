import logging
from typing import List, Literal, Optional, Tuple
import re
from io import BytesIO
import zipfile

import discord
import sqlalchemy as sa
from discord.ext import commands
from sqlalchemy_searchable import search as pg_search
from discord.ext.alternatives import literal_converter

from luhack_bot import constants
from luhack_bot.db.models import Image, Writeup
from luhack_bot.utils.checks import is_authed

logger = logging.getLogger(__name__)


class Writeups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await is_authed(ctx)

    @staticmethod
    def tag_url(tag):
        return constants.writeups_base_url / "tag" / tag

    @staticmethod
    def writeup_url(slug):
        return constants.writeups_base_url / "view" / slug

    async def get_writeup(self, title: str) -> Optional[Writeup]:
        return await Writeup.query.where(Writeup.title == title).gino.first()

    async def search_writeups(self, search: str) -> List[Writeup]:
        """Search for writeups, return top 3 matching."""
        return await pg_search(Writeup.query, search, sort=True).limit(3).gino.all()

    def can_edit_writeup(self, writeup: Writeup, user_id: int) -> bool:
        return (
            writeup.author_id == user_id
            or self.bot.luhack_guild()
            .get_member(user_id)
            .guild_permissions.administrator
        )

    def format_writeup(self, writeup: Writeup) -> str:
        author = self.bot.luhack_guild().get_member(writeup.author_id)
        tags = ", ".join(writeup.tags)

        return f'"{writeup.title}" ({self.writeup_url(writeup.slug)}) by {author}, tags: `{tags}`'

    async def show_similar_writeups(
        self, ctx, title: str, found_message: str = "Possible writeups are:"
    ):
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

        tags = " ".join(
            "[{}]({})".format(tag, self.tag_url(tag).human_repr())
            for tag in writeup.tags
        )

        embed = discord.Embed(
            title=writeup.title,
            timestamp=writeup.creation_date,
            colour=discord.Colour.blue(),
            author=self.bot.luhack_guild().get_member(writeup.author_id),
        )
        embed.add_field(name="tags", value=tags, inline=False)
        embed.add_field(name="link", value=self.writeup_url(writeup.slug), inline=False)
        embed.add_field(name="last edited", value=writeup.edit_date, inline=False)

        await ctx.send(embed=embed)

    @staticmethod
    def extract_and_update_images_for_export(content: str) -> Tuple[str, List[str]]:
        images = []

        def repl(m):
            images.append(m.group(2))
            return f"(.{m.group(1)})"

        new_content = re.sub(r"\((/images/([A-z0-9\-]+)\.\w+)\)",
                             repl, content)

        return new_content, images

    @staticmethod
    def preprocess_writeups_for_export(writeups: List[Writeup]) -> List[str]:
        images = []

        for writeup in writeups:
            (w, i) = Writeups.extract_and_update_images_for_export(writeup.content)
            images.extend(i)
            writeup.content = w

        return images

    @staticmethod
    async def fetch_images_for_export(images: List[str]) -> List[Image]:
        return await Image.query.where(Image.id.in_(images)).gino.all()

    @writeups.command()
    async def export(self, ctx, op: Optional[Literal["slugs", "tags"]] = "slugs", *tags_or_slugs: str):
        """Export writeups into a zip containing their markdown content and their images.

        op decides what writeups to get:
          - slugs: export all writeups from the given list of writeup slugs
          - tags: export all writeups that have all of the given tags
        """

        writeup_filter = (
            Writeup.tags.contains
            if op == "tags"
            else Writeup.slug.in_
        )

        writeups = (
            await Writeup.query.where(writeup_filter(tags_or_slugs))
            .order_by(sa.desc(Writeup.creation_date))
            .gino.all()
        )

        image_ids = self.preprocess_writeups_for_export(writeups)

        images = await self.fetch_images_for_export(image_ids)

        zip_data = BytesIO()

        with zipfile.ZipFile(zip_data, mode="w",
                             compression=zipfile.ZIP_DEFLATED) as f:
            for writeup in writeups:
                f.writestr(f"{writeup.slug}.md", writeup.content)

            for image in images:
                f.writestr(f"images/{image.id}.{image.filetype}", image.image)

        zip_data.seek(0)

        await ctx.send("Here you go", file=discord.File(zip_data, "writeups.zip"))


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

    @commands.command(aliases=["site_link"])
    async def site_token(self, ctx):
        """Deprecated, sign in to the site via OAuth now."""

        await ctx.send("Sign in to the site using OAuth now!")


def setup(bot):
    bot.add_cog(Writeups(bot))
