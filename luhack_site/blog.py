from itertools import groupby
from textwrap import shorten
from typing import List, Tuple
import calendar

import sqlalchemy as sa
import ujson
from sqlalchemy_searchable import search as pg_search
from sqlalchemy_searchable import search_manager
from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.routing import Router

from luhack_site.utils import abort, redirect_response
from luhack_site.authorization import can_edit
from luhack_site.forms import PostForm
from luhack_site.markdown import highlight_markdown, length_constrained_plaintext_markdown
from luhack_site.templater import templates
from luhack_site.images import encoded_existing_images
from luhack_site.content_logger import log_edit, log_create, log_delete

from luhack_bot.db.models import Blog, db

router = Router()


async def blogs_grouped() -> List[Tuple[str, List[Tuple[str, List[Blog]]]]]:
    """Return all blogs grouped by year and month in the format [(year, [(month, [blog])])]"""
    all_blogs = await Blog.query.order_by(sa.desc(Blog.creation_date)).gino.all()

    def group_monthly(blogs):
        for k, v in groupby(blogs, key=lambda blog: blog.creation_date.month):
            yield (calendar.month_name[k], list(v))

    def group_yearly(blogs):
        for k, v in groupby(blogs, key=lambda blog: blog.creation_date.year):
            yield (str(k), list(v))

    return [(year, list(group_monthly(year_blogs))) for year, year_blogs in group_yearly(all_blogs)]


@router.route("/")
async def blog_index(request: HTTPConnection):
    latest = await Blog.query.order_by(sa.desc(Blog.creation_date)).gino.all()

    rendered = [
        (w, length_constrained_plaintext_markdown(w.content))
        for w in latest
    ]

    grouped_blogs = await blogs_grouped()

    return templates.TemplateResponse(
        "blog/index.j2", {"request": request, "blog": rendered, "grouped_blogs": grouped_blogs}
    )


@router.route("/view/{slug}")
async def blog_view(request: HTTPConnection):
    slug = request.path_params["slug"]

    blog = await Blog.query.where(Blog.slug == slug).gino.first()

    if blog is None:
        return abort(404, "Blog not found")

    rendered = highlight_markdown(blog.content)

    return templates.TemplateResponse(
        "blog/view.j2", {"blog": blog, "request": request, "rendered": rendered}
    )


@router.route("/tag/{tag}")
async def blog_by_tag(request: HTTPConnection):
    tag = request.path_params["tag"]

    blog = (
        await Blog.query.where(Blog.tags.contains([tag]))
        .order_by(sa.desc(Blog.creation_date))
        .gino.all()
    )

    rendered = [
        (w, length_constrained_plaintext_markdown(w.content))
        for w in blog
    ]

    grouped_blogs = await blogs_grouped()

    return templates.TemplateResponse(
        "blog/index.j2", {"request": request, "blog": rendered, "grouped_blogs": grouped_blogs}
    )


async def get_all_tags():
    tags = (
        await sa.select([sa.column("tag")])
        .select_from(Blog)
        .select_from(sa.func.unnest(Blog.tags).alias("tag"))
        .group_by(sa.column("tag"))
        .order_by(sa.func.count())
        .gino.all()
    )

    return [i for (i,) in tags]


@router.route("/tags")
async def blog_all_tags(request: HTTPConnection):
    tags = await get_all_tags()

    grouped_blogs = await blogs_grouped()

    return templates.TemplateResponse(
        "blog/tag_list.j2", {"request": request, "tags": tags, "grouped_blogs": grouped_blogs}
    )


@router.route("/search")
async def blog_search(request: HTTPConnection):
    s_query = request.query_params.get("search", "")

    # sorry about this
    query = pg_search(sa.select([Blog]), s_query, sort=True)
    query = query.column(
        sa.func.ts_headline(
            search_manager.options["regconfig"],
            Blog.content,
            sa.func.tsq_parse(search_manager.options["regconfig"], s_query),
            f"StartSel=**,StopSel=**,MaxWords=70,MinWords=30,MaxFragments=3",
        ).label("headline")
    )

    blog = await query.as_scalar().gino.all()

    def build_blog(r):
        """we get back a RowProxy so manually construct the blog from it."""

        blog = Blog(
            id=r.id,
            title=r.title,
            slug=r.slug,
            tags=r.tags,
            content=r.content,
            creation_date=r.creation_date,
            edit_date=r.edit_date,
        )

        return blog

    blog = [(build_blog(r), r.headline) for r in blog]

    rendered = [
        (w, length_constrained_plaintext_markdown(headline))
        for (w, headline) in blog
    ]

    grouped_blogs = await blogs_grouped()

    return templates.TemplateResponse(
        "blog/index.j2", {"request": request, "blog": rendered, "query": s_query, "grouped_blogs": grouped_blogs}
    )


@router.route("/delete/{id:int}")
@requires("admin", redirect="not_admin")
async def blog_delete(request: HTTPConnection):
    id = request.path_params["id"]

    blog = await Blog.get(id)

    if blog is None:
        return abort(404, "Blog not found")

    if not can_edit(request):
        return abort(400)

    await blog.delete()
    await log_delete("blog", blog.title, request.user.username)

    return redirect_response(url=request.url_for("blog_index"))


@router.route("/new")
class NewBlog(HTTPEndpoint):
    @requires("admin", redirect="not_admin")
    async def get(self, request: HTTPConnection):
        form = PostForm()

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "blog/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
                "existing_tags": tags,
            },
        )

    @requires("admin", redirect="not_admin")
    async def post(self, request: HTTPConnection):
        form = await request.form()

        form = PostForm(form)

        is_valid = form.validate()

        if (
            await Blog.query.where(Blog.title == form.title.data).gino.first()
            is not None
        ):
            is_valid = False
            form.title.errors.append(
                f"A blog with the title '{form.title.data}' already exists."
            )

        if is_valid:
            blog = await Blog.create_auto(
                title=form.title.data, tags=form.tags.data, content=form.content.data
            )

            url = request.url_for("blog_view", slug=blog.slug)
            await log_create("blog", blog.title, request.user.username, url)

            return redirect_response(url=url)

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "blog/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
                "existing_tags": tags,
            },
        )


@router.route("/edit/{id:int}")
class EditBlog(HTTPEndpoint):
    @requires("admin", redirect="not_admin")
    async def get(self, request: HTTPConnection):
        id = request.path_params["id"]

        blog = await Blog.get(id)

        if blog is None:
            return abort(404, "Blog not found")

        if not can_edit(request):
            return abort(400)

        form = PostForm(title=blog.title, tags=blog.tags, content=blog.content)

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "blog/edit.j2",
            {
                "request": request,
                "form": form,
                "blog": blog,
                "existing_images": images,
                "existing_tags": tags,
            },
        )

    @requires("admin", redirect="not_admin")
    async def post(self, request: HTTPConnection):
        id = request.path_params["id"]

        blog = await Blog.get(id)

        if blog is None:
            return abort(404, "Blog not found")

        if not can_edit(request):
            return abort(400)

        form = await request.form()

        form = PostForm(form)

        if form.validate():
            await blog.update_auto(
                title=form.title.data, tags=form.tags.data, content=form.content.data
            ).apply()

            url = request.url_for("blog_view", slug=blog.slug)
            await log_edit("blog", blog.title, request.user.username, url)

            return redirect_response(url=url)

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "blog/edit.j2",
            {
                "request": request,
                "form": form,
                "blog": blog,
                "existing_images": images,
                "existing_tags": tags,
            },
        )
