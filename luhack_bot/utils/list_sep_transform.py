from discord import app_commands
import discord
from typing import Callable, Coroutine, Any


class ListSepTransformer(app_commands.Transformer):
    async def transform(
        self, interaction: discord.Interaction, value: str
    ) -> list[str]:
        return [x.strip() for x in value.split(",")]


def list_sep_choices(
    inner: Callable[
        [discord.Interaction, str], Coroutine[Any, Any, list[app_commands.Choice[str]]]
    ]
) -> Callable[
    [discord.Interaction, str], Coroutine[Any, Any, list[app_commands.Choice[str]]]
]:
    async def impl(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        *prev_completed, to_complete = [item.strip() for item in current.split(",")]

        completed = await inner(interaction, to_complete)

        return [
            app_commands.Choice(
                name=", ".join([*prev_completed, c.name]),
                value=", ".join([*prev_completed, c.value]),
            )
            for c in completed
        ]

    return impl
