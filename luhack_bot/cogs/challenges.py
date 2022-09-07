import logging
import textwrap
from datetime import datetime
from typing import Any, Callable, Coroutine, List, Literal, Optional, Tuple, TypeVar

import discord
import sqlalchemy as sa
from discord.ext import commands
from discord import app_commands
from gino.loader import ColumnLoader
from tabulate import tabulate

from luhack_bot import constants
from luhack_bot.db.helpers import text_search
from luhack_bot.db.models import Challenge, CompletedChallenge, User, db
from luhack_bot.utils.checks import is_admin_int, is_authed, is_authed_int

logger = logging.getLogger(__name__)


T = TypeVar("T")


def split_on(l: List[Tuple[T, bool]]) -> Tuple[List[T], List[T]]:
    a, b = [], []
    for v, k in l:
        (a if k else b).append(v)
    return a, b


async def title_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not current:
        results = await (
            db.select([Challenge.title, Challenge.slug])
            .where(sa.not_(Challenge.hidden))
            .order_by(Challenge.title)
            .limit(25)
            .gino.all()
        )
    else:
        similarity = sa.func.levenshtein_less_equal(
            current, Challenge.title, 0, 1, 1, 10
        ).label("sim")

        inner = db.select([Challenge, similarity]).alias("inner")

        results = await (
            db.select([inner.c.title, inner.c.slug, inner.c.sim])
            .select_from(inner)
            .where(inner.c.sim < 10)
            .where(sa.not_(inner.c.hidden))
            .limit(25)
            .order_by(sa.asc(inner.c.sim))
            .gino.load((inner.c.title, inner.c.slug))
            .all()
        )

    return [app_commands.Choice(name=name, value=value) for name, value in results]


async def tag_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    tags = (
        sa.select([sa.column("tag")])
        .select_from(Challenge)
        .select_from(sa.func.unnest(Challenge.tags).alias("tag"))
        .group_by(sa.column("tag"))
        .order_by(sa.func.count())
        .cte("tags")
    )

    if not current:
        results = await (
            db.select([tags.c.tag])
            .select_from(tags)
            .order_by(tags.c.tag)
            .limit(25)
            .gino.load((ColumnLoader(tags.c.tag),))
            .all()
        )
    else:

        similarity = sa.func.levenshtein_less_equal(
            current, tags.c.tag, 0, 1, 1, 10
        ).label("sim")

        inner = db.select([tags.c.tag, similarity]).alias("inner")

        results = await (
            db.select([inner.c.tag, inner.c.sim])
            .select_from(inner)
            .where(inner.c.sim < 10)
            .limit(25)
            .order_by(sa.asc(inner.c.sim))
            .gino.load((ColumnLoader(tags.c.tag),))
            .all()
        )

    return [app_commands.Choice(name=name, value=name) for name, in results]


class ListSepTransformer(app_commands.Transformer):
    async def transform(
        self, interaction: discord.Interaction, value: str
    ) -> list[str]:
        return [x.strip() for x in value.split(",")]


def list_sep_choices(
    inner: Callable[
        [discord.Interaction, str], Coroutine[Any, Any, list[app_commands.Choice[str]]]
    ]
) -> Callable[
    [discord.Interaction, str], Coroutine[Any, Any, list[app_commands.Choice[str]]]
]:
    async def impl(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        *prev_completed, to_complete = [item.strip() for item in current.split(",")]

        completed = await inner(interaction, to_complete)

        return [
            app_commands.Choice(
                name=", ".join([*prev_completed, c.name]),
                value=", ".join([*prev_completed, c.value]),
            )
            for c in completed
        ]

    return impl


CURRENT_SEASON = 2


def tag_url(tag):
    return constants.challenges_base_url / "tag" / tag


def challenge_url(slug):
    return constants.challenges_base_url / "view" / slug


class Challenges(commands.GroupCog, name="challenge"):
    """Challenge related commands"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction):
        return await is_authed_int(interaction)

    async def get_challenge(self, slug: str) -> Optional[Challenge]:
        return (
            await Challenge.query.where(Challenge.slug == slug)
            .where(sa.not_(Challenge.hidden))
            .gino.first()
        )

    async def search_challenges(self, search: str) -> List[Challenge]:
        """Search for challenges, return top 3 matching."""
        return (
            await text_search(
                Challenge.query.where(sa.not_(Challenge.hidden)), search, sort=True
            )
            .limit(3)
            .gino.all()
        )

    def format_challenge(self, challenge: Challenge) -> str:
        tags = " ".join(challenge.tags)
        tags_fmt = f" [tags: {tags}]" if tags else ""
        return f"{challenge.title} [points: {challenge.points}] ({challenge_url(challenge.slug)}){tags_fmt}"

    async def show_similar_challenges(
        self, ctx, title: str, found_message: str = "Possible challenges are:"
    ):
        """Shows similar challenges to a user."""

        similar = [
            self.format_challenge(i) for i in await self.search_challenges(title)
        ]

        if similar:
            await ctx.send("{} \n{}\n".format(found_message, "\n".join(similar)))
        else:
            await ctx.send("No challenges found, sorry.")

    @app_commands.command(name="get")
    @app_commands.describe(title="The title of the challenge")
    @app_commands.autocomplete(title=title_autocomplete)
    async def view_challenge(self, interaction: discord.Interaction, title: str):
        """Get a challenge by title"""
        challenge = await self.get_challenge(title)

        if challenge is None:
            await interaction.response.send_message("Dunno")
            return

        await interaction.response.send_message(self.format_challenge(challenge))

    @app_commands.command(name="tags")
    @app_commands.describe(tag="The tag to link to")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def by_tag(self, interaction: discord.Interaction, tag: str):
        """Get a link to challenges with a tag."""
        await interaction.response.send_message(tag_url(tag))

    @app_commands.command(name="stats")
    @app_commands.describe(
        tag_condition="Filter by challenges with EVERY tag or ANY tag, defautls to EVERY"
    )
    @app_commands.describe(
        season="The season to get the stats in, defaults to the latest"
    )
    @app_commands.describe(tags="Tags to search for, separate with ',' to add many")
    @app_commands.autocomplete(tags=list_sep_choices(tag_autocomplete))
    async def stats(
        self,
        interaction: discord.Interaction,
        *,
        tag_condition: Optional[Literal["every", "any"]] = "every",
        season: Optional[int] = CURRENT_SEASON,
        tags: Optional[app_commands.Transform[list[str], ListSepTransformer]],
    ):
        """View the most and lest solved challenges.

        tag_condition decides whether to filter by challenges that have EVERY
        specified tag, or ANY of the specified tags, defaults to EVERY.

        Note that specifying no tags with "every" filters to all challenges,
        while no tags with "any" filters to zero challenges!
        """

        if tags is None:
            tags = []

        tag_filter = (
            Challenge.tags.contains
            if tag_condition == "every"
            else Challenge.tags.overlap
        )

        count = sa.func.count(CompletedChallenge.challenge_id).label("count")
        rank = sa.func.dense_rank().over(order_by=sa.desc("count")).label("rank")

        q_most = (
            db.select([Challenge.title, Challenge.points, count, Challenge.hidden])
            .select_from(Challenge.outerjoin(CompletedChallenge))
            .where(tag_filter(tags))
            .where(CompletedChallenge.season == season)
            .group_by(Challenge.id)
            .alias("inner")
        )

        hidden_check_most = sa.case([(q_most.c.hidden, "X")], else_="").label(
            "hidden_check"
        )

        most = await (
            db.select(
                [
                    rank,
                    q_most.c.title,
                    q_most.c.count,
                    q_most.c.points,
                    hidden_check_most,
                ]
            )
            .select_from(q_most)
            .limit(5)
            .order_by(sa.desc(q_most.c.count))
            .gino.load(
                (
                    rank,
                    q_most.c.title,
                    ColumnLoader(q_most.c.count),
                    q_most.c.points,
                    hidden_check_most,
                )
            )
            .all()
        )

        q_least = (
            db.select([Challenge.title, Challenge.points, count, Challenge.hidden])
            .select_from(Challenge.outerjoin(CompletedChallenge))
            .where(tag_filter(tags))
            .where(CompletedChallenge.season == season)
            .group_by(Challenge.id)
            .alias("inner")
        )

        hidden_check_least = sa.case([(q_least.c.hidden, "X")], else_="").label(
            "hidden_check"
        )

        least = await (
            db.select(
                [
                    rank,
                    q_least.c.title,
                    q_least.c.count,
                    q_least.c.points,
                    hidden_check_least,
                ]
            )
            .select_from(q_least)
            .order_by(sa.asc(q_least.c.count))
            .limit(5)
            .gino.load(
                (
                    rank,
                    q_least.c.title,
                    ColumnLoader(q_least.c.count),
                    q_least.c.points,
                    hidden_check_least,
                )
            )
            .all()
        )

        most_table = tabulate(
            most,
            headers=["Rank", "Challenge Title", "Solves", "Points", "Hidden"],
            tablefmt="github",
        )

        least_table = tabulate(
            least,
            headers=["Rank", "Challenge Title", "Solves", "Points", "Hidden"],
            tablefmt="github",
        )

        msg = textwrap.dedent(
            """
            ```md
            # Most Solved Challenges in season {season}
            {most_table}

            # Least Solved Challenges in season {season}
            {least_table}
            ```
            """
        ).format(most_table=most_table, least_table=least_table, season=season)

        await interaction.response.send_message(msg)

    @app_commands.command(name="leaderboard")
    @app_commands.describe(
        tag_condition="Filter by challenges with EVERY tag or ANY tag, defautls to EVERY"
    )
    @app_commands.describe(
        season="The season to get the stats in, defaults to the latest"
    )
    @app_commands.describe(tags="Tags to search for, separate with ',' to add many")
    @app_commands.autocomplete(tags=list_sep_choices(tag_autocomplete))
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        *,
        tag_condition: Optional[Literal["every", "any"]] = "every",
        season: Optional[int] = CURRENT_SEASON,
        tags: Optional[app_commands.Transform[list[str], ListSepTransformer]],
    ):
        """View the leaderboard for completed challenges.

        tag_condition decides whether to filter by challenges that have EVERY
        specified tag, or ANY of the specified tags, defaults to EVERY.

        Note that specifying no tags with "every" filters to all challenges,
        while no tags with "any" filters to zero challenges!
        """

        if tags is None:
            tags = []

        tag_filter = (
            Challenge.tags.contains
            if tag_condition == "every"
            else Challenge.tags.overlap
        )

        score = sa.func.sum(Challenge.points).label("score")
        count = sa.func.count(Challenge.points).label("count")
        rank = sa.func.dense_rank().over(order_by=sa.desc("score")).label("rank")

        q = (
            db.select([User.discord_id, score, count])
            .select_from(User.join(CompletedChallenge).join(Challenge))
            .where(tag_filter(tags))
            .where(CompletedChallenge.season == season)
            .group_by(User.discord_id)
            .alias("inner")
        )

        scores = await (
            db.select([q.c.discord_id, q.c.score, q.c.count, rank])
            .select_from(q)
            .order_by(sa.desc(q.c.score))
            .limit(10)
            .gino.load(
                (
                    q.c.discord_id,
                    ColumnLoader(q.c.score),
                    ColumnLoader(q.c.count),
                    ColumnLoader(rank),
                )
            )
            .all()
        )

        scores_formatted = [
            [r, self.bot.get_user(uid), s, c] for (uid, s, c, r) in scores
        ]

        table = tabulate(
            scores_formatted,
            headers=["Rank", "Username", "Score", "Solved Challenges"],
            tablefmt="github",
        )

        await interaction.response.send_message(
            f"Scoreboard for season {season}: ```\n{table}\n```"
        )

    @app_commands.command(name="info")
    @app_commands.describe(
        season="The season to get the stats in, defaults to the latest"
    )
    async def info(
        self,
        interaction: discord.Interaction,
        *,
        season: Optional[int] = CURRENT_SEASON,
    ):
        """Get info about your solved and unsolved challenges."""

        solved_challenges = (
            db.select([CompletedChallenge.challenge_id])
            .where(CompletedChallenge.discord_id == interaction.user.id)
            .where(CompletedChallenge.season == season)
            .cte("solved_challenges")
        )

        solved = (
            sa.exists()
            .where(solved_challenges.c.challenge_id == Challenge.id)
            .label("solved")
        )

        score = sa.func.sum(Challenge.points).label("score")
        scores_q = (
            db.select([User.discord_id, score])
            .select_from(User.outerjoin(CompletedChallenge).outerjoin(Challenge))
            .where(CompletedChallenge.season == season)
            .group_by(User.discord_id)
            .cte("scores")
        )
        my_score = (
            db.select([sa.func.coalesce(scores_q.c.score, 0)])
            .select_from(scores_q)
            .where(scores_q.c.discord_id == interaction.user.id)
        )
        rank_value = await (
            db.select([sa.func.count(sa.distinct(scores_q.c.score)) + 1])
            .where(scores_q.c.score > my_score)
            .gino.scalar()
        )

        info = await (
            db.select([Challenge, solved])
            .where(sa.not_(Challenge.hidden))
            .gino.load((Challenge, ColumnLoader(solved)))
            .all()
        )

        solved, unsolved = split_on(info)

        points = sum(c.points for c in solved)
        count = len(solved)

        solved_msg = ", ".join(c.title for c in solved) or "No solves"
        unsolved_msg = ", ".join(c.title for c in unsolved) or "All solved"

        msg = textwrap.dedent(
            f"""
            Challenge info for {interaction.user} in season {season}:

            Solves: {count}
            Points: {points}
            Rank: {rank_value}
            Solved: `{solved_msg}`
            Unsolved: `{unsolved_msg}`
        """
        )

        await interaction.response.send_message(msg)

    @app_commands.command(name="claim")
    @app_commands.describe(flag="The flag or answer to submit")
    @app_commands.describe(title="The title of the challenge")
    @app_commands.rename(title="challenge")
    @app_commands.autocomplete(title=title_autocomplete)
    async def claim(
        self,
        interaction: discord.Interaction,
        *,
        flag: str,
        title: Optional[str] = None,
    ):
        """Claim a challenge or flag. You'll need to specify the challenge name if you're submitting a non flag answer."""
        flag = flag.strip()

        if title is None:
            challenge = (
                await Challenge.query.where(Challenge.flag == flag)
                .where(sa.not_(Challenge.hidden))
                .gino.first()
            )

        else:
            challenge = await self.get_challenge(title)

        if challenge is None:
            await interaction.response.send_message(
                "That doesn't look to be a valid flag or answer.", ephemeral=True
            )
            return

        if not (challenge.answer == flag or challenge.flag == flag):
            # if this is an answer solve
            await interaction.response.send_message(
                "That isn't the correct answer, sorry.", ephemeral=True
            )
            return

        if challenge.depreciated:
            msg = textwrap.dedent(
                """
                Congrats on completing the challenge!

                Unfortunately you can no longer score points for this challenge because
                a writeup has been released, or for other reasons.
                """
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        already_claimed = await CompletedChallenge.query.where(
            (CompletedChallenge.discord_id == interaction.user.id)
            & (CompletedChallenge.challenge_id == challenge.id)
            & (CompletedChallenge.season == CURRENT_SEASON)
        ).gino.first()

        if already_claimed is not None:
            await interaction.response.send_message(
                "It looks like you've already claimed this flag.", ephemeral=True
            )
            return

        await CompletedChallenge.create(
            discord_id=interaction.user.id,
            challenge_id=challenge.id,
            season=CURRENT_SEASON,
        )
        await interaction.response.send_message(
            f"Congrats, you've completed this challenge and have been awarded {challenge.points} points!",
            ephemeral=True,
        )


@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
class ChallengeAdmin(commands.GroupCog, name="challenge_admin"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction):
        return is_admin_int(interaction)

    @app_commands.command(name="admin")
    @app_commands.describe(op="Operation to perform")
    @app_commands.describe(
        tag_condition="Filter by challenges with EVERY tag or ANY tag, defautls to EVERY"
    )
    @app_commands.describe(tags="Tags to search for, separate with ',' to add many")
    @app_commands.autocomplete(tags=list_sep_choices(tag_autocomplete))
    async def admin(
        self,
        interaction: discord.Interaction,
        *,
        op: Literal["hide", "unhide", "depreciate", "undepreciate"],
        tag_condition: Optional[Literal["every", "any"]] = "every",
        tags: Optional[app_commands.Transform[list[str], ListSepTransformer]],
    ):
        """Perform admin operations on challenges.

        op decides what to do:
          - hide: set the hidden flag
          - unhide: unset the hidden flag, also resets the creation date
                    of the challenge to be the current time.
          - depreciate: set the depreciated flag (challenge can no longer be solved)
          - undepreciate: unset the depreciated flag

        tag_condition decides whether to filter by challenges that have EVERY
        specified tag, or ANY of the specified tags, defaults to EVERY.

        Note that specifying no tags with "every" filters to all challenges,
        while no tags with "any" filters to zero challenges!
        """

        tag_filter = (
            Challenge.tags.contains
            if tag_condition == "every"
            else Challenge.tags.overlap
        )

        update = {
            "hide": {"hidden": True},
            "unhide": {"hidden": False, "creation_date": sa.func.now()},
            "depreciate": {"depreciated": True},
            "undepreciate": {"depreciated": False},
        }[op]

        (r, _) = (
            await Challenge.update.values(**update)
            .where(tag_filter(tags))
            .gino.status()
        )
        r = strip_prefix(r, "UPDATE ")

        await interaction.response.send_message(f"Updated {r} challenges")

    @app_commands.command(name="announce")
    @app_commands.describe(op="Operation to perform")
    @app_commands.describe(
        tag_condition="Filter by challenges with EVERY tag or ANY tag, defautls to EVERY"
    )
    @app_commands.describe(tags="Tags to search for, separate with ',' to add many")
    @app_commands.autocomplete(tags=list_sep_choices(tag_autocomplete))
    async def announce(
        self,
        interaction: discord.Interaction,
        *,
        op: Literal["available", "depreciated"],
        tag_condition: Optional[Literal["every", "any"]] = "every",
        tags: Optional[app_commands.Transform[list[str], ListSepTransformer]],
    ):
        """Perform admin announcement of challenges.

        op decides what to do:
          - avail: announces that the challenge is now available to be completed
          - depreciated: announces that the challenge can no longer be solved

        tag_condition decides whether to filter by challenges that have EVERY
        specified tag, or ANY of the specified tags, defaults to EVERY.

        Note that specifying no tags with "every" filters to all challenges,
        while no tags with "any" filters to zero challenges!
        """

        tag_filter = (
            Challenge.tags.contains
            if tag_condition == "every"
            else Challenge.tags.overlap
        )

        challenges = (
            await Challenge.query.where(sa.not_(Challenge.hidden))
            .where(tag_filter(tags))
            .order_by(Challenge.creation_date.desc(), Challenge.id.desc())
            .gino.all()
        )

        data_fn = {
            "available": lambda c: (
                "Challenge Available",
                f"The challenge '{c.title}' has just been made available!",
                discord.Colour.green(),
            ),
            "depreciated": lambda c: (
                "Challenge Depreciated",
                f"The challenge '{c.title}' has depreciated and is no longer solvable for points!",
                discord.Colour.dark_red(),
            ),
        }[op]

        channel = self.bot.luhack_guild().get_channel(
            constants.challenge_log_channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "Couldn't find challenge log channel?", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Okay, announcing {len(challenges)} challenges"
        )

        for challenge in challenges:
            title, desc, colour = data_fn(challenge)
            embed = discord.Embed(
                title=title,
                description=desc,
                color=colour,
                timestamp=datetime.utcnow(),
                url=str(challenge_url(challenge.slug)),
            )
            await channel.send(embed=embed)


def strip_prefix(s, pre):
    if s.startswith(pre):
        return s[len(pre) :]
    return s


async def setup(bot):
    await bot.add_cog(Challenges(bot))
    await bot.add_cog(
        ChallengeAdmin(bot), guilds=[discord.Object(id=constants.luhack_guild_id)]
    )
