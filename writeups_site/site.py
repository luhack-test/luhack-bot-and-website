from os import getenv
from pathlib import Path
from textwrap import shorten

from dotenv import load_dotenv

import sqlalchemy as sa
from sqlalchemy_searchable import search as pg_search

from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.staticfiles import StaticFiles
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Mount
from starlette.responses import PlainTextResponse
from starlette.templating import Jinja2Templates

from writeups_site.middleware import TokenAuthBackend
from writeups_site.markdown import highlight_markdown, plaintext_markdown
from luhack_bot.db.helpers import init_db
from luhack_bot.db.models import User, Writeup, db

root_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(root_dir / "templates"))

load_dotenv(root_dir.parent)

app = Starlette(debug=True)

app.add_middleware(AuthenticationMiddleware, backend=TokenAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=getenv("TOKEN_SECRET"))

statics = StaticFiles(directory=str(root_dir / "static"))
app.mount("/static", statics, name="static")


def abort(status: int, reason: str = ""):
    return PlainTextResponse(reason, status)


@app.on_event("startup")
async def startup():
    await init_db()


@app.route("/")
async def index(request: HTTPConnection):
    latest = (
        await Writeup.load(author=User)
        .order_by(sa.desc(Writeup.creation_date))
        .limit(20)
        .gino.all()
    )

    rendered = [
        (w, shorten(plaintext_markdown(w.content), width=300, placeholder="..."))
        for w in latest
    ]

    return templates.TemplateResponse(
        "index.j2", {"request": request, "writeups": rendered}
    )


@app.route("/writeup/{slug}")
async def view(request: HTTPConnection):
    slug = request.path_params["slug"]

    writeup = await Writeup.load(author=User).where(Writeup.slug == slug).gino.first()

    if writeup is None:
        return abort(404, "Writeup not found")

    rendered = highlight_markdown(writeup.content)

    return templates.TemplateResponse(
        "writeup.j2", {"writeup": writeup, "request": request, "rendered": rendered}
    )


@app.route("/tag/{tag}")
async def tag(request: HTTPConnection):
    tag = request.path_params["tag"]

    writeups = (
        await Writeup.load(author=User)
        .where(Writeup.tags.contains([tag]))
        .order_by(sa.desc(Writeup.creation_date))
        .gino.all()
    )

    rendered = [
        (w, shorten(plaintext_markdown(w.content), width=300, placeholder="..."))
        for w in writeups
    ]

    return templates.TemplateResponse(
        "index.j2", {"request": request, "writeups": rendered}
    )


@app.route("/tags")
async def tags(request: HTTPConnection):
    tags = (
        await sa.select([sa.column("tag")])
        .select_from(Writeup)
        .select_from(sa.func.unnest(Writeup.tags).alias("tag"))
        .group_by(sa.column("tag"))
        .order_by(sa.func.count())
        .gino.all()
    )

    tags = [i for (i,) in tags]

    return templates.TemplateResponse("tag_list.j2", {"request": request, "tags": tags})


@app.route("/search")
async def search(request: HTTPConnection):
    query = request.query_params["search"]

    writeups = await pg_search(Writeup.load(author=User), query, sort=True).gino.all()

    rendered = [
        (w, shorten(plaintext_markdown(w.content), width=300, placeholder="..."))
        for w in writeups
    ]

    return templates.TemplateResponse(
        "index.j2", {"request": request, "writeups": rendered}
    )


@app.route("/delete/{id:int}")
@requires("authenticated")
async def delete(request: HTTPConnection):
    id = request.path_params["id"]

    writeup = await Writeup.get(id)

    if writeup is None:
        return abort(404, "Writeup not found")

    if not request.user.is_admin and writeup.author_id != request.user.discord_id:
        return abort(400)

    await Writeup.delete.where(Writeup.id == id).gino.status()
