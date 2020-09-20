from itertools import groupby
from textwrap import shorten
from typing import List, Tuple
import calendar

import sqlalchemy as sa
from gino.loader import ColumnLoader

from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.routing import Router

from luhack_site.utils import abort, redirect_response
from luhack_site.authorization import can_edit
from luhack_site.forms import ChallengeForm
from luhack_site.markdown import highlight_markdown, plaintext_markdown
from luhack_site.templater import templates
from luhack_site.images import encoded_existing_images
from luhack_site.content_logger import log_edit, log_create, log_delete

from luhack_bot.db.models import db, Challenge, CompletedChallenge

router = Router()


async def challenges_grouped() -> List[Tuple[str, List[Tuple[str, List[Challenge]]]]]:
    """Return all challenges grouped by year and month in the format [(year, [(month, [challenge])])]"""
    all_challenges = await Challenge.query.order_by(
        sa.desc(Challenge.creation_date)
    ).gino.all()

    def group_monthly(challenges):
        for k, v in groupby(
            challenges, key=lambda challenge: challenge.creation_date.month
        ):
            yield (calendar.month_name[k], list(v))

    def group_yearly(challenges):
        for k, v in groupby(
            challenges, key=lambda challenge: challenge.creation_date.year
        ):
            yield (str(k), list(v))

    return [
        (year, list(group_monthly(year_challenges)))
        for year, year_challenges in group_yearly(all_challenges)
    ]


@router.route("/")
async def challenge_index(request: HTTPConnection):
    solves = sa.func.count(CompletedChallenge.challenge_id).label("solves")

    challenges = await (
        db.select([Challenge, solves])
        .select_from(Challenge.outerjoin(CompletedChallenge))
        .group_by(Challenge.id)
        .order_by(sa.desc(Challenge.creation_date))
        .gino.load((Challenge, ColumnLoader(solves)))
        .all()
    )

    rendered = [
        (
            w,
            shorten(plaintext_markdown(w.content), width=800, placeholder="..."),
            solves,
        )
        for (w, solves) in challenges
    ]

    grouped_challenges = await challenges_grouped()

    return templates.TemplateResponse(
        "challenge/index.j2",
        {
            "request": request,
            "challenges": rendered,
            "grouped_challenges": grouped_challenges,
        },
    )


@router.route("/view/{slug}")
async def challenge_view(request: HTTPConnection):
    slug = request.path_params["slug"]

    solves = sa.func.count(CompletedChallenge.challenge_id).label("solves")

    challenge = await (
        db.select([Challenge, solves])
        .select_from(Challenge.outerjoin(CompletedChallenge))
        .group_by(Challenge.id)
        .where(Challenge.slug == slug)
        .gino.load((Challenge, ColumnLoader(solves)))
        .first()
    )

    if challenge is None:
        return abort(404, "Challenge not found")

    challenge, solves = challenge

    rendered = highlight_markdown(challenge.content)

    return templates.TemplateResponse(
        "challenge/view.j2",
        {"challenge": challenge, "request": request, "rendered": rendered, "solves": solves},
    )


@router.route("/delete/{id:int}")
@requires("admin", redirect="not_admin")
async def challenge_delete(request: HTTPConnection):
    id = request.path_params["id"]

    challenge = await Challenge.get(id)

    if challenge is None:
        return abort(404, "Challenge not found")

    if not can_edit(request):
        return abort(400)

    await challenge.delete()
    await log_delete("challenge", challenge.title, request.user.username)

    return redirect_response(url=request.url_for("challenge_index"))


@router.route("/new")
class NewChallenge(HTTPEndpoint):
    @requires("admin", redirect="not_admin")
    async def get(self, request: HTTPConnection):
        form = ChallengeForm()

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "challenge/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
            },
        )

    @requires("admin", redirect="not_admin")
    async def post(self, request: HTTPConnection):
        form = await request.form()

        form = ChallengeForm(form)

        is_valid = form.validate()

        if (
            await Challenge.query.where(Challenge.title == form.title.data).gino.first()
            is not None
        ):
            is_valid = False
            form.errors.setdefault("title", []).append(
                f"A challenge with the title '{form.title.data}' already exists."
            )

        if is_valid:
            challenge = await Challenge.create_auto(
                title=form.title.data,
                content=form.content.data,
                flag=form.flag.data,
                points=form.points.data,
            )

            url = request.url_for("challenge_view", slug=challenge.slug)
            await log_create("challenge", challenge.title, request.user.username, url)

            return redirect_response(url=url)

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "challenge/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
            },
        )


@router.route("/edit/{id:int}")
class EditChallenge(HTTPEndpoint):
    @requires("admin", redirect="not_admin")
    async def get(self, request: HTTPConnection):
        id = request.path_params["id"]

        challenge = await Challenge.get(id)

        if challenge is None:
            return abort(404, "Challenge not found")

        if not can_edit(request):
            return abort(400)

        form = ChallengeForm(
            title=challenge.title,
            content=challenge.content,
            flag=challenge.flag,
            points=challenge.points,
        )

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "challenge/edit.j2",
            {
                "request": request,
                "form": form,
                "challenge": challenge,
                "existing_images": images,
            },
        )

    @requires("admin", redirect="not_admin")
    async def post(self, request: HTTPConnection):
        id = request.path_params["id"]

        challenge = await Challenge.get(id)

        if challenge is None:
            return abort(404, "Challenge not found")

        if not can_edit(request):
            return abort(400)

        form = await request.form()

        form = ChallengeForm(form)

        if form.validate():
            await challenge.update_auto(
                title=form.title.data,
                content=form.content.data,
                flag=form.flag.data,
                points=form.points.data,
            ).apply()

            url = request.url_for("challenge_view", slug=challenge.slug)
            await log_edit("challenge", challenge.title, request.user.username, url)

            return redirect_response(url=url)

        images = await encoded_existing_images(request)

        return templates.TemplateResponse(
            "challenge/edit.j2",
            {
                "request": request,
                "form": form,
                "challenge": challenge,
                "existing_images": images,
            },
        )
