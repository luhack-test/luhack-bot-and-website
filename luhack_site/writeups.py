from textwrap import shorten
from typing import List, Tuple

import sqlalchemy as sa
import ujson
from sqlalchemy_searchable import search as pg_search
from sqlalchemy_searchable import search_manager
from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.responses import RedirectResponse
from starlette.routing import Router

from luhack_site.utils import abort
from luhack_site.authorization import can_edit
from luhack_site.forms import PostForm
from luhack_site.markdown import highlight_markdown, plaintext_markdown
from luhack_site.templater import templates
from luhack_site.images import encoded_existing_images

from luhack_bot.db.models import User, Writeup, db

router = Router()


@router.route("/")
async def writeups_index(request: HTTPConnection):
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
        "writeups/index.j2", {"request": request, "writeups": rendered}
    )


@router.route("/view/{slug}")
async def writeups_view(request: HTTPConnection):
    slug = request.path_params["slug"]

    writeup = await Writeup.load(author=User).where(Writeup.slug == slug).gino.first()

    if writeup is None:
        return abort(404, "Writeup not found")

    rendered = highlight_markdown(writeup.content)

    return templates.TemplateResponse(
        "writeups/view.j2",
        {"writeup": writeup, "request": request, "rendered": rendered},
    )


@router.route("/tag/{tag}")
async def writeups_by_tag(request: HTTPConnection):
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
        "writeups/index.j2", {"request": request, "writeups": rendered}
    )


@router.route("/user/{user}")
async def writeups_by_user(request: HTTPConnection):
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
        "writeups/index.j2", {"request": request, "writeups": rendered}
    )


async def get_all_tags():
    tags = (
        await sa.select([sa.column("tag")])
        .select_from(Writeup)
        .select_from(sa.func.unnest(Writeup.tags).alias("tag"))
        .group_by(sa.column("tag"))
        .order_by(sa.func.count())
        .gino.all()
    )

    return [i for (i,) in tags]


@router.route("/tags")
async def writeups_all_tags(request: HTTPConnection):
    tags = await get_all_tags()

    return templates.TemplateResponse(
        "writeups/tag_list.j2", {"request": request, "tags": tags}
    )


@router.route("/search")
async def writeups_search(request: HTTPConnection):
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
        "writeups/index.j2",
        {"request": request, "writeups": rendered, "query": s_query},
    )


@router.route("/delete/{id:int}")
@requires("authenticated", redirect="need_auth")
async def writeups_delete(request: HTTPConnection):
    id = request.path_params["id"]

    writeup = await Writeup.get(id)

    if writeup is None:
        return abort(404, "Writeup not found")

    if not can_edit(request, writeup.author_id):
        return abort(400)

    await Writeup.delete.where(Writeup.id == id).gino.status()

    return RedirectResponse(url=request.url_for("writeups_index"))


@router.route("/new")
class NewWriteup(HTTPEndpoint):
    @requires("authenticated", redirect="need_auth")
    async def get(self, request: HTTPConnection):
        form = PostForm()

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "writeups/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
                "existing_tags": tags,
            },
        )

    @requires("authenticated", redirect="need_auth")
    async def post(self, request: HTTPConnection):
        form = await request.form()

        form = PostForm(form)

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

            return RedirectResponse(url=request.url_for("writeups_view", slug=writeup.slug))

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "writeups/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
                "existing_tags": tags,
            },
        )


@router.route("/edit/{id:int}")
class EditWriteup(HTTPEndpoint):
    @requires("authenticated", redirect="need_auth")
    async def get(self, request: HTTPConnection):
        id = request.path_params["id"]

        writeup = await Writeup.get(id)

        if writeup is None:
            return abort(404, "Writeup not found")

        if not can_edit(request, writeup.author_id):
            return abort(400)

        form = PostForm(
            title=writeup.title, tags=writeup.tags, content=writeup.content
        )

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "writeups/edit.j2",
            {
                "request": request,
                "form": form,
                "writeup": writeup,
                "existing_images": images,
                "existing_tags": tags,
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

        form = PostForm(form)

        if form.validate():
            await writeup.update_auto(
                author_id=request.user.discord_id,
                title=form.title.data,
                tags=form.tags.data,
                content=form.content.data,
            ).apply()

            return RedirectResponse(url=request.url_for("writeups_view", slug=writeup.slug))

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "writeups/edit.j2",
            {
                "request": request,
                "form": form,
                "writeup": writeup,
                "existing_images": images,
                "existing_tags": tags,
            },
        )
