import imghdr
from os import getenv
from pathlib import Path
from textwrap import shorten
from typing import List, Tuple

import sqlalchemy as sa
from dotenv import load_dotenv

import ujson
from sqlalchemy_searchable import search as pg_search
from sqlalchemy_searchable import search_manager
from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import (
    PlainTextResponse,
    RedirectResponse,
    Response,
    UJSONResponse,
)
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from luhack_bot.db.helpers import init_db
from luhack_bot.db.models import Image, User, Writeup, db

from writeups_site import converters
from writeups_site.forms import WriteupForm
from writeups_site.markdown import highlight_markdown, plaintext_markdown
from writeups_site.middleware import TokenAuthBackend

converters.inject()

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


def can_edit(request, author_id):
    if not request.user.is_authenticated:
        return False

    return request.user.is_admin or author_id == request.user.discord_id


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


@app.route("/plzauth")
async def need_auth(request: HTTPConnection):
    return templates.TemplateResponse("plzauth.j2", {"request": request})


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
    s_query = request.query_params.get("search", "")

    # sorry about this
    query = pg_search(sa.select([Writeup.join(User)]), s_query, sort=True)
    query = query.column(
        sa.func.ts_headline(
            search_manager.options["regconfig"],
            Writeup.content,
            sa.func.tsq_parse(search_manager.options["regconfig"], s_query),
            f"StartSel=**,StopSel=**,MaxWords=70,MinWords=30,MaxFragments=3",
        ).label("headline")
    )

    writeups = await query.as_scalar().gino.all()

    def build_writeup(r):
        """we get back a RowProxy so manually construct the writeup from it."""

        author = User(discord_id=r.discord_id, username=r.username, email=r.email)

        writeup = Writeup(
            id=r.id,
            author_id=r.author_id,
            title=r.title,
            slug=r.slug,
            tags=r.tags,
            content=r.content,
            creation_date=r.creation_date,
            edit_date=r.edit_date,
        )

        writeup.author = author
        return writeup

    writeups = [(build_writeup(r), r.headline) for r in writeups]

    rendered = [
        (w, shorten(plaintext_markdown(headline), width=300, placeholder="..."))
        for (w, headline) in writeups
    ]

    return templates.TemplateResponse(
        "index.j2", {"request": request, "writeups": rendered, "query": s_query}
    )


@app.route("/sign_out")
async def sign_out(request: HTTPConnection):
    request.session.pop("token", None)

    return RedirectResponse(url=request.url_for("index"))


@app.route("/delete/{id:int}")
@requires("authenticated", redirect="need_auth")
async def delete(request: HTTPConnection):
    id = request.path_params["id"]

    writeup = await Writeup.get(id)

    if writeup is None:
        return abort(404, "Writeup not found")

    if not can_edit(request, writeup.author_id):
        return abort(400)

    await Writeup.delete.where(Writeup.id == id).gino.status()

    return RedirectResponse(url=request.url_for("index"))


@app.route("/images/{file_name:file}", name="images")
class Images(HTTPEndpoint):
    async def get(self, request: HTTPConnection):
        uuid, ext = request.path_params["file_name"]

        image = await Image.get(uuid)

        if image.filetype != ext:
            return abort(404)

        return Response(image.image, media_type=f"image/{image.filetype}")

    @requires("authenticated")
    async def delete(self, request: HTTPConnection):
        uuid, ext = request.path_params["file_name"]

        image = await Image.get(uuid)

        if image.filetype != ext:
            return abort(404)

        if not can_edit(request, image.author_id):
            return abort(400)

        await image.delete()

        return Response()


@app.route("/upload-image", methods=["POST"])
@requires("authenticated", redirect="need_auth")
async def upload_image(request: HTTPConnection):
    form = await request.form()

    file_contents = await form["file"].read()

    filetype = imghdr.what("dynamic", file_contents)
    if filetype not in {"png", "jpeg", "gif", "webp"}:
        return abort(400, "Bad image type")

    file = await Image.create(
        author_id=request.user.discord_id, filetype=filetype, image=file_contents
    )

    return UJSONResponse({"filename": f"{file.id}.{filetype}"})


async def get_existing_images(author_id: int) -> List[Tuple[str, str]]:
    return (
        await sa.select([Image.id, Image.filetype])
        .where(Image.author_id == author_id)
        .gino.all()
    )


async def encoded_existing_images(request: HTTPConnection) -> str:
    images = await get_existing_images(request.user.discord_id)
    images = [
        {
            "filename": f"{id}.{ext}",
            "path": request.url_for("images", file_name=(id, ext)),
        }
        for (id, ext) in images
    ]
    return ujson.dumps(images)


@app.route("/new")
class NewWriteup(HTTPEndpoint):
    @requires("authenticated", redirect="need_auth")
    async def get(self, request: HTTPConnection):
        form = WriteupForm()

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "new.j2", {"request": request, "form": form, "existing_images": images}
        )

    @requires("authenticated", redirect="need_auth")
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

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "new.j2", {"request": request, "form": form, "existing_images": images}
        )


@app.route("/edit/{id:int}")
class EditWriteup(HTTPEndpoint):
    @requires("authenticated", redirect="need_auth")
    async def get(self, request: HTTPConnection):
        id = request.path_params["id"]

        writeup = await Writeup.get(id)

        if writeup is None:
            return abort(404, "Writeup not found")

        if not can_edit(request, writeup.author_id):
            return abort(400)

        form = WriteupForm(
            title=writeup.title, tags=writeup.tags, content=writeup.content
        )

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "edit.j2",
            {
                "request": request,
                "form": form,
                "writeup": writeup,
                "existing_images": images,
            },
        )

    @requires("authenticated", redirect="need_auth")
    async def post(self, request: HTTPConnection):
        id = request.path_params["id"]

        writeup = await Writeup.get(id)

        if writeup is None:
            return abort(404, "Writeup not found")

        if not can_edit(request, writeup.author_id):
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

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "edit.j2",
            {
                "request": request,
                "form": form,
                "writeup": writeup,
                "existing_images": images,
            },
        )
