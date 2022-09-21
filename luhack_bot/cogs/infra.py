from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import aioretry
import httpx
import rapidfuzz
import cachetools
import pygtrie
import discord
import tailscale
from tailscale import Tailscale
from discord.ext import commands
from luhack_bot import secrets
import sqlalchemy.dialects.postgresql as psa

from luhack_bot.cogs.challenges import logging
from luhack_bot.cogs.verification import app_commands
from luhack_bot.db.helpers import db
from luhack_bot.db.models import Machine
from luhack_bot.utils.async_cache import async_cached
from luhack_bot.utils.checks import is_admin_int, is_authed_int


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from luhack_bot.bot import LUHackBot


async def devices() -> list[tailscale.Device]:
    async with Tailscale(tailnet=secrets.tailnet, api_key=secrets.tailscale_key) as ts:
        return list((await ts.devices()).values())


@async_cached(cache=cachetools.TTLCache(maxsize=1024, ttl=60))
async def target_devices() -> list[tailscale.Device]:
    return [dev for dev in await devices() if dev.tags and "tag:target" in dev.tags]


async def get_device(name: str) -> Optional[tailscale.Device]:
    devices = await target_devices()

    # me when I build a dict just to query it once
    for dev in devices:
        if dev.name == name:
            return dev


def attach_desc(trie: pygtrie.CharTrie, name: str) -> str:
    if (desc := trie.longest_prefix(name)) is not None and desc.value is not None:
        return desc.value
    return ""


@async_cached(cache=cachetools.TTLCache(maxsize=1024, ttl=60))
async def target_devices_descriptions(
    query: Optional[str] = None,
) -> list[tuple[str, tailscale.Device]]:
    machines = await db.all(Machine.query)
    t = pygtrie.CharTrie({m.hostname: m.description for m in machines})

    devices = await target_devices()
    names = [dev.name for dev in devices]

    if query is not None:
        matching = {
            h
            for h, _, _ in rapidfuzz.process.extract(
                query, names, limit=25, score_cutoff=0.5
            )
        }
    else:
        matching = set(names)

    return [(attach_desc(t, dev.name), dev) for dev in devices if dev.name in matching]


def format_name(name: str) -> str:
    return name.split(".")[0]


async def machine_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    query = current if current else None
    machines = await target_devices_descriptions(query)

    return [
        app_commands.Choice(
            name=f"{desc} ({format_name(dev.name)})" if desc else format_name(dev.name),
            value=dev.name,
        )
        for desc, dev in machines
    ]


async def hostname_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    query = current if current else None
    machines = await target_devices_descriptions(query)

    return [
        app_commands.Choice(
            name=dev.hostname,
            value=dev.hostname,
        )
        for _, dev in machines
    ]


def retry_policy(info: aioretry.RetryInfo) -> aioretry.RetryPolicyStrategy:
    if info.fails > 3:
        return True, 0

    return False, info.fails * 0.1


@aioretry.retry(retry_policy)
async def generate_invite(node: str):
    cookies = {
        "tailscale-authstate2": secrets.tailscale_authstate2,
        "tailcontrol": secrets.tailscale_tailcontrol,
    }
    async with httpx.AsyncClient(
        base_url="https://login.tailscale.com/admin/api",
        cookies=cookies,
        http2=True,
        timeout=0.5,
    ) as client:
        self_ = await client.get("/self")
        self_.raise_for_status()
        csrf = self_.headers["x-csrf-token"]

        logger.debug("tailscale response: %s", self_.text)

        headers = {"X-CSRF-Token": csrf}
        body = {"node": node, "includeExitNodes": False}
        invite = await client.post("/invite/new", headers=headers, json=body)
        invite.raise_for_status()

        return invite.json()["data"]["code"]


@app_commands.guild_only()
class Infra(commands.GroupCog, name="infra"):
    def __init__(self, bot: LUHackBot):
        self.bot = bot

        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction):
        return await is_authed_int(interaction)

    @app_commands.command(name="join")
    @app_commands.describe(name="The machine to join")
    @app_commands.autocomplete(name=machine_autocomplete)
    async def join_server(self, interaction: discord.Interaction, *, name: str):
        """Get an invite to one of our target practice systems."""

        if (device := await get_device(name)) is None:
            await interaction.response.send_message(
                "I don't know that device", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        msg = f"{interaction.user} requested access to node {name}"
        logger.info(msg)
        await self.bot.log_message(msg)

        invite = await generate_invite(device.device_id)
        button = discord.ui.Button(
            url=f"https://login.tailscale.com/admin/invite/{invite}",
            label="Click here to join",
        )
        await interaction.followup.send(view=discord.ui.View().add_item(button))

    @app_commands.command(name="describe")
    @app_commands.describe(hostname="Hostname to describe")
    @app_commands.describe(desc="Short description of the box")
    @app_commands.autocomplete(hostname=hostname_autocomplete)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.check(is_admin_int)
    async def describe_server(
        self, interaction: discord.Interaction, *, hostname: str, desc: str
    ):
        """Set the description for a target machine."""

        q = psa.insert(Machine).values(hostname=hostname, description=desc)
        q = q.on_conflict_do_update(
            index_elements=[Machine.hostname],
            set_=dict(description=q.excluded.description),
        )
        await q.gino.status()

        await interaction.response.send_message(
            f"Set description of {hostname} to {desc}"
        )

        target_devices_descriptions.clear()

    @app_commands.command(name="delete_description")
    @app_commands.autocomplete(hostname=hostname_autocomplete)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.check(is_admin_int)
    async def undescribe_server(
        self, interaction: discord.Interaction, *, hostname: str
    ):
        """Unset the description for a target machine."""

        await Machine.delete.where(Machine.hostname == hostname).gino.status()

        await interaction.response.send_message(f"Unset description of {hostname}")

        target_devices_descriptions.clear()

    @app_commands.command(name="clear_cache")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.check(is_admin_int)
    async def clear_cache(self, interaction: discord.Interaction):
        """Clear the tailscale device cache."""

        target_devices.clear()

        await interaction.response.send_message(f"Cleared", ephemeral=True)


async def setup(bot: LUHackBot):
    await bot.add_cog(Infra(bot))
