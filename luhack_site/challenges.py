from itertools import groupby
from textwrap import shorten
from typing import List, Tuple
import calendar

import sqlalchemy as sa
import ujson
from gino.loader import ColumnLoader

from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.routing import Router

from luhack_site.utils import abort, redirect_response
from luhack_site.authorization import can_edit
from luhack_site.forms import ChallengeForm, AnswerForm
from luhack_site.markdown import highlight_markdown_unsafe, plaintext_markdown
from luhack_site.templater import templates
from luhack_site.images import encoded_existing_images
from luhack_site.content_logger import log_edit, log_create, log_delete

from luhack_bot.db.models import db, Challenge, CompletedChallenge

router = Router()


async def challenges_grouped() -> List[Tuple[str, List[Tuple[str, List[Challenge]]]]]:
    """Return all challenges grouped by year and month in the format [(year, [(month, [challenge])])]"""
    all_challenges = (
        await Challenge.query.order_by(
            Challenge.creation_date.desc(), Challenge.id.desc()
        )
        .where(sa.not_(Challenge.hidden))
        .gino.all()
    )

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


def should_skip_challenge(c: Challenge, is_admin: bool) -> bool:
    return c.hidden and not is_admin


@router.route("/")
async def challenge_index(request: HTTPConnection):
    solves = sa.func.count(CompletedChallenge.challenge_id).label("solves")

    select = [Challenge, solves]
    columns = (Challenge, ColumnLoader(solves))

    if request.user.is_authenticated:
        solved_challenges = (
            db.select([CompletedChallenge.challenge_id])
            .where(CompletedChallenge.discord_id == request.user.discord_id)
            .cte("solved_challenges")
        )

        solved = (
            sa.exists()
            .where(solved_challenges.c.challenge_id == Challenge.id)
            .label("solved")
        )

        select.append(solved)
        columns = (*columns, ColumnLoader(solved))

    challenges = await (
        db.select(select)
        .select_from(Challenge.outerjoin(CompletedChallenge))
        .group_by(Challenge.id)
        .order_by(Challenge.creation_date.desc(), Challenge.id.desc())
        .gino.load(columns)
        .all()
    )

    rendered = [
        (
            w,
            shorten(plaintext_markdown(w.content), width=800, placeholder="..."),
            solves,
            did_solve and did_solve[0],
        )
        for (w, solves, *did_solve) in challenges
        if not should_skip_challenge(w, request.user.is_admin)
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

    if should_skip_challenge(challenge, request.user.is_admin):
        return abort(404, "Challenge not found")

    if request.user.is_authenticated:
        solved_challenge = await CompletedChallenge.query.where(
            (CompletedChallenge.discord_id == request.user.discord_id)
            & (CompletedChallenge.challenge_id == challenge.id)
        ).gino.first()
    else:
        solved_challenge = False

    rendered = highlight_markdown_unsafe(challenge.content)

    return templates.TemplateResponse(
        "challenge/view.j2",
        {
            "challenge": challenge,
            "request": request,
            "rendered": rendered,
            "solves": solves,
            "submit_form": AnswerForm(),
            "solved_challenge": solved_challenge,
        },
    )


@router.route("/tag/{tag}")
async def challenge_by_tag(request: HTTPConnection):
    tag = request.path_params["tag"]

    solves = sa.func.count(CompletedChallenge.challenge_id).label("solves")

    challenges = await (
        db.select([Challenge, solves])
        .select_from(Challenge.outerjoin(CompletedChallenge))
        .group_by(Challenge.id)
        .where(Challenge.tags.contains([tag]))
        .order_by(Challenge.creation_date.desc(), Challenge.id.desc())
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
        if not should_skip_challenge(w, request.user.is_admin)
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


async def get_all_tags():
    tags = (
        await sa.select([sa.column("tag")])
        .select_from(Challenge)
        .select_from(sa.func.unnest(Challenge.tags).alias("tag"))
        .where(sa.not_(Challenge.hidden))
        .group_by(sa.column("tag"))
        .order_by(sa.func.count())
        .gino.all()
    )

    return [i for (i,) in tags]


@router.route("/tags")
async def challenge_all_tags(request: HTTPConnection):
    tags = await get_all_tags()

    grouped_challenges = await challenges_grouped()

    return templates.TemplateResponse(
        "challenge/tag_list.j2",
        {"request": request, "tags": tags, "grouped_challenges": grouped_challenges},
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


@router.route("/submit/{id:int}", methods=["POST"])
@requires("authenticated", redirect="need_auth")
async def challenge_submit_answer(request: HTTPConnection):
    id = request.path_params["id"]

    form = await request.form()
    form = AnswerForm(form)

    is_valid = form.validate()

    answer = form.answer.data

    solves = sa.func.count(CompletedChallenge.challenge_id).label("solves")

    challenge = await (
        db.select([Challenge, solves])
        .select_from(Challenge.outerjoin(CompletedChallenge))
        .group_by(Challenge.id)
        .where(Challenge.id == id)
        .gino.load((Challenge, ColumnLoader(solves)))
        .first()
    )

    if challenge is None:
        return abort(404, "Challenge not found")

    challenge, solves = challenge

    if should_skip_challenge(challenge, request.user.is_admin):
        return abort(404, "Challenge not found")

    if (challenge.answer or challenge.flag) != answer:
        is_valid = False
        form.answer.errors.append("Incorrect answer.")

    # TODO? change this to a flash message
    if challenge.depreciated:
        is_valid = False
        form.answer.errors.append("Correct, but this challenge is depreciated sorry.")

    already_claimed = await CompletedChallenge.query.where(
        (CompletedChallenge.discord_id == request.user.discord_id)
        & (CompletedChallenge.challenge_id == challenge.id)
    ).gino.first()

    if already_claimed is not None:
        # shouldn't see the form anyway
        is_valid = False
        form.answer.errors.append("You've already solved this challenge.")

    if is_valid:
        await CompletedChallenge.create(
            discord_id=request.user.discord_id, challenge_id=challenge.id
        )

        return redirect_response(url=request.url_for("challenge_view", slug=challenge.slug))

    rendered = highlight_markdown_unsafe(challenge.content)

    return templates.TemplateResponse(
        "challenge/view.j2",
        {
            "challenge": challenge,
            "request": request,
            "rendered": rendered,
            "solves": solves,
            "submit_form": form,
        },
    )


@router.route("/new")
class NewChallenge(HTTPEndpoint):
    @requires("admin", redirect="not_admin")
    async def get(self, request: HTTPConnection):
        form = ChallengeForm()

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "challenge/new.j2",
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

        form = ChallengeForm(form)

        is_valid = form.validate()

        if (
            await Challenge.query.where(Challenge.title == form.title.data).gino.first()
            is not None
        ):
            is_valid = False
            form.title.errors.append(
                f"A challenge with the title '{form.title.data}' already exists."
            )

        if is_valid:
            f_a = form.flag_or_answer.data
            flag, answer = (f_a, None) if form.is_flag.data else (None, f_a)

            challenge = await Challenge.create_auto(
                title=form.title.data,
                content=form.content.data,
                flag=flag,
                answer=answer,
                hidden=form.hidden.data,
                depreciated=form.depreciated.data,
                points=form.points.data,
                tags=form.tags.data,
            )

            url = request.url_for("challenge_view", slug=challenge.slug)

            if not challenge.hidden:
                await log_create(
                    "challenge", challenge.title, request.user.username, url
                )

            return redirect_response(url=url)

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "challenge/new.j2",
            {
                "request": request,
                "form": form,
                "existing_images": images,
                "existing_tags": tags,
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
            flag_or_answer=challenge.flag or challenge.answer,
            is_flag=challenge.flag is not None,
            hidden=challenge.hidden,
            depreciated=challenge.depreciated,
            points=challenge.points,
            tags=challenge.tags,
        )

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "challenge/edit.j2",
            {
                "request": request,
                "form": form,
                "challenge": challenge,
                "existing_images": images,
                "existing_tags": tags,
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
            f_a = form.flag_or_answer.data
            flag, answer = (f_a, None) if form.is_flag.data else (None, f_a)

            await challenge.update_auto(
                title=form.title.data,
                content=form.content.data,
                flag=flag,
                answer=answer,
                hidden=form.hidden.data,
                depreciated=form.depreciated.data,
                points=form.points.data,
                tags=form.tags.data,
            ).apply()

            url = request.url_for("challenge_view", slug=challenge.slug)
            if not challenge.hidden:
                await log_edit("challenge", challenge.title, request.user.username, url)

            return redirect_response(url=url)

        images = await encoded_existing_images(request)
        tags = ujson.dumps(await get_all_tags())

        return templates.TemplateResponse(
            "challenge/edit.j2",
            {
                "request": request,
                "form": form,
                "challenge": challenge,
                "existing_images": images,
                "existing_tags": tags,
            },
        )
