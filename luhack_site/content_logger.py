from datetime import datetime
from typing import Optional

import aiohttp

from discord.colour import Colour
from discord.embeds import Embed
from discord.webhook import Webhook

from luhack_site import settings

webhook_url = settings.LOG_WEBHOOK


async def log_to_webhook(
    *, content: Optional[str] = None, embed: Optional[Embed] = None
):
    assert bool(content) != bool(embed)

    async with aiohttp.ClientSession() as sess:
        webhook = Webhook.from_url(webhook_url, session=sess)
        if content:
            await webhook.send(content=content)
        elif embed:
            await webhook.send(embed=embed)


async def log_edit(type_: str, name: str, author: str, url: str):
    embed = Embed(
        title=f"Edited {type_}: {name}",
        color=Colour.blue(),
        timestamp=datetime.utcnow(),
        url=url,
    )
    embed.set_author(name=author)
    await log_to_webhook(embed=embed)


async def log_create(type_: str, name: str, author: str, url: str):
    embed = Embed(
        title=f"Created {type_}: {name}",
        color=Colour.green(),
        timestamp=datetime.utcnow(),
        url=url,
    )
    embed.set_author(name=author)
    await log_to_webhook(embed=embed)


async def log_delete(type_: str, name: str, author: str):
    embed = Embed(
        title=f"Deleted {type_}: {name}",
        color=Colour.red(),
        timestamp=datetime.utcnow(),
    )
    embed.set_author(name=author)
    await log_to_webhook(embed=embed)
