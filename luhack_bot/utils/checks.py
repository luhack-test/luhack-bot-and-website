import discord
from discord.ext import commands

from luhack_bot.db.models import User
from luhack_bot.constants import luhack_guild_id, disciple_role_id


def in_channel(channel_id: int):
    def inner(ctx: commands.Context):
        if ctx.channel.id != channel_id:
            raise commands.CheckFailure(f"This command is only usable inside <#{channel_id}>")
        return True
    return inner


def is_in_luhack(ctx: commands.Context) -> bool:
    """Ensure a member is in the luhack guild."""
    if ctx.bot.get_guild(luhack_guild_id).get_member(ctx.author.id) is None:
        raise commands.CheckFailure("It looks like you're not in the luhack guild, what are you doing?")

    return True

def is_disciple_or_admin(ctx: commands.Context) -> bool:
    """Ensure a member is a disciple or admin."""
    if ctx.guild is None or ctx.guild.id != luhack_guild_id:
        raise commands.CheckFailure("You can only use this command in the luhack guild")

    is_disciple = discord.utils.get(ctx.author.roles, id=disciple_role_id) is not None
    is_admin = ctx.author.guild_permissions.administrator

    if not (is_admin or is_disciple):
        raise commands.CheckFailure("You must be an admin or disciple to use this command.")

    return True

async def is_authed(ctx: commands.Context) -> bool:
    """Ensure a member is registered with LUHack."""

    user = await User.get(ctx.author.id)

    if user is None:
        raise commands.CheckFailure("It looks like you're not registed with luhack, go and register yourself.")

    return True
