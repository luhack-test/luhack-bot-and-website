from os import getenv
from pathlib import Path
from textwrap import shorten

from dotenv import load_dotenv

import sqlalchemy as sa
from sqlalchemy_searchable import search as pg_search

from starlette.endpoints import HTTPEndpoint
from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.staticfiles import StaticFiles
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Mount
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from writeups_site.middleware import TokenAuthBackend, User
from writeups_site.markdown import highlight_markdown, plaintext_markdown
from writeups_site.forms import WriteupForm

from luhack_bot.db.helpers import init_db
from luhack_bot.db.models import User, Writeup, db

root_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(root_dir / "templates"))

load_dotenv(root_dir.parent)

app = Starlette()

app.add_middleware(AuthenticationMiddleware, backend=TokenAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=getenv("TOKEN_SECRET"))

statics = StaticFiles(directory=str(root_dir / "static"))
app.mount("/static", statics, name="static")


def abort(status: int, reason: str = ""):
    return PlainTextResponse(reason, status)


def can_edit(request, writeup):
    if not request.user.is_authenticated:
        return False

    return request.user.is_admin or writeup.author_id == request.user.discord_id


templates.env.globals.update(can_edit=can_edit)


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


@app.route("/user/{user}")
async def user(request: HTTPConnection):
    user = request.path_params["user"]

    writeups = (
        await Writeup.load(author=User)
        .where(User.username == user)
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
    query = request.query_params.get("search", "")

    writeups = await pg_search(Writeup.load(author=User), query, sort=True).gino.all()

    rendered = [
        (w, shorten(plaintext_markdown(w.content), width=300, placeholder="..."))
        for w in writeups
    ]

    return templates.TemplateResponse(
        "index.j2", {"request": request, "writeups": rendered, "query": query}
    )


@app.route("/sign_out")
async def sign_out(request: HTTPConnection):
    request.session.pop("token", None)

    return RedirectResponse(url=request.url_for("index"))


@app.route("/delete/{id:int}")
@requires("authenticated")
async def delete(request: HTTPConnection):
    id = request.path_params["id"]

    writeup = await Writeup.get(id)

    if writeup is None:
        return abort(404, "Writeup not found")

    if not can_edit(request, writeup):
        return abort(400)

    await Writeup.delete.where(Writeup.id == id).gino.status()

    return RedirectResponse(url=request.url_for("index"))


@app.route("/new")
class NewWriteup(HTTPEndpoint):
    @requires("authenticated")
    async def get(self, request: HTTPConnection):
        form = WriteupForm()

        return templates.TemplateResponse("new.j2", {"request": request, "form": form})

    @requires("authenticated")
    async def post(self, request: HTTPConnection):
        form = await request.form()

        form = WriteupForm(form)

        is_valid = form.validate()

        if (
            await Writeup.query.where(Writeup.title == form.title.data).gino.first()
            is not None
        ):
            is_valid = False
            form.errors.setdefault("title", []).append(
                f"A writeup with the title '{form.title.data}' already exists."
            )

        if is_valid:
            writeup = await Writeup.create_auto(
                author_id=request.user.discord_id,
                title=form.title.data,
                tags=form.tags.data,
                content=form.content.data,
            )

            return RedirectResponse(url=request.url_for("view", slug=writeup.slug))

        return templates.TemplateResponse("new.j2", {"request": request, "form": form})


@app.route("/edit/{id:int}")
class EditWriteup(HTTPEndpoint):
    @requires("authenticated")
    async def get(self, request: HTTPConnection):
        id = request.path_params["id"]

        writeup = await Writeup.get(id)

        if writeup is None:
            return abort(404, "Writeup not found")

        if not can_edit(request, writeup):
            return abort(400)

        form = WriteupForm(
            title=writeup.title, tags=writeup.tags, content=writeup.content
        )

        return templates.TemplateResponse(
            "edit.j2", {"request": request, "form": form, "writeup": writeup}
        )

    @requires("authenticated")
    async def post(self, request: HTTPConnection):
        id = request.path_params["id"]

        writeup = await Writeup.get(id)

        if writeup is None:
            return abort(404, "Writeup not found")

        if not can_edit(request, writeup):
            return abort(400)

        form = await request.form()

        form = WriteupForm(form)

        if form.validate():
            await writeup.update_auto(
                author_id=request.user.discord_id,
                title=form.title.data,
                tags=form.tags.data,
                content=form.content.data,
            ).apply()

            return RedirectResponse(url=request.url_for("view", slug=writeup.slug))

        return templates.TemplateResponse(
            "edit.j2", {"request": request, "form": form, "writeup": writeup}
        )
