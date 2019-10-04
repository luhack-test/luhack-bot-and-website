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
    if ctx.bot.luhack_guild().get_member(ctx.author.id) is None:
        raise commands.CheckFailure("It looks like you're not in the luhack guild, what are you doing?")

    return True

def is_admin(ctx: commands.Context) -> bool:
    """Ensure a member is a disciple or admin."""
    member_in_luhack = ctx.bot.get_guild(luhack_guild_id).get_member(ctx.author.id)
    if member_in_luhack is None:
        raise commands.CheckFailure("You must be an admin or disciple to use this command.")

    is_disciple = discord.utils.get(member_in_luhack.roles, id=disciple_role_id) is not None
    is_admin = member_in_luhack.guild_permissions.administrator

    if not (is_admin or is_disciple):
        raise commands.CheckFailure("You must be an admin or disciple to use this command.")

    return True

async def is_authed(ctx: commands.Context) -> bool:
    """Ensure a member is registered with LUHack."""

    user = await User.get(ctx.author.id)

    if user is None:
        raise commands.CheckFailure("It looks like you're not registed with luhack, go and register yourself.")

    return True

# async def can_use_verif_commands(ctx: commands.Context) -> bool:
#     """Ensure a member is allowed to use the verification commands (is flagged or new)."""

#     existing_user = await User.get(ctx.author.id)
#     is_flagged = (
#         existing_user is not None and existing_user.flagged_for_deletion is not None
#     )

#     if existing_user is not None and not is_flagged:
#         raise commands.CheckFailure("It seems you've already registered.")

#     return True
