from discord.ext import commands

from luhack_bot.constants import luhack_guild_id


def is_in_luhack(ctx: commands.Context) -> bool:
    """Ensure a member is in the luhack guild."""
    if ctx.bot.get_guild(luhack_guild_id).get_member(ctx.author.id) is None:
        raise commands.CheckFailure("It looks like you're not in the luhack guild, what are you doing?")

    return True
