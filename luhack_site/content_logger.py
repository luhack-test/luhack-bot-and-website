from os import getenv
from datetime import datetime

import aiohttp

from discord.colour import Colour
from discord.embeds import Embed
from discord.webhook import Webhook, AsyncWebhookAdapter

from luhack_site import load_env

webhook_url = getenv("LOG_WEBHOOK")


async def log_to_webhook(*, content=None, embed=None):
    async with aiohttp.ClientSession() as sess:
        webhook = Webhook.from_url(webhook_url, adapter=AsyncWebhookAdapter(sess))
        await webhook.send(content=content, embed=embed)


async def log_edit(type_: str, name: str, author: str, url: str):
    embed = Embed(
        title=f"Edited {type_}: {name}", color=Colour.blue(), timestamp=datetime.utcnow(), url=url
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
        title=f"Deleted {type_}: {name}", color=Colour.red(), timestamp=datetime.utcnow()
    )
    embed.set_author(name=author)
    await log_to_webhook(embed=embed)
