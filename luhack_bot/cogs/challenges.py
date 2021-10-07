import logging
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, List, Literal, Optional, Tuple, TypeVar

import discord
import sqlalchemy as sa
from discord.ext import commands
from gino.loader import ColumnLoader
from sqlalchemy_searchable import search as pg_search
from discord.ext.alternatives import literal_converter as _
from tabulate import tabulate

from luhack_bot import constants
from luhack_bot.db.models import Challenge, CompletedChallenge, User, db
from luhack_bot.utils.checks import is_admin, is_authed

logger = logging.getLogger(__name__)


T = TypeVar("T")


def split_on(l: List[Tuple[T, bool]]) -> Tuple[List[T], List[T]]:
    a, b = [], []
    for v, k in l:
        (a if k else b).append(v)
    return a, b


if TYPE_CHECKING:
    ChallengeName = Challenge
else:

    class ChallengeName(commands.Converter):
        async def convert(self, ctx, arg: str):
            r = (
                await Challenge.query.where(Challenge.slug == arg)
                .where(sa.not_(Challenge.hidden))
                .gino.first()
            )

            if r is None:
                raise commands.BadArgument(f"{arg} is not a challenge")

            return r


CURRENT_SEASON = 2


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await is_authed(ctx)

    @staticmethod
    def tag_url(tag):
        return constants.challenges_base_url / "tag" / tag

    @staticmethod
    def challenge_url(slug):
        return constants.challenges_base_url / "view" / slug

    async def get_challenge(self, title: str) -> Optional[Challenge]:
        return (
            await Challenge.query.where(Challenge.title == title)
            .where(sa.not_(Challenge.hidden))
            .gino.first()
        )

    async def search_challenges(self, search: str) -> List[Challenge]:
        """Search for challenges, return top 3 matching."""
        return (
            await pg_search(
                Challenge.query.where(sa.not_(Challenge.hidden)), search, sort=True
            )
            .limit(3)
            .gino.all()
        )

    def format_challenge(self, challenge: Challenge) -> str:
        tags = " ".join(challenge.tags)
        tags_fmt = f" [tags: {tags}]" if tags else ""
        return f"{challenge.title} [points: {challenge.points}] ({self.challenge_url(challenge.slug)}){tags_fmt}"

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

    @commands.group(aliases=["challenge", "ch"], invoke_without_command=True)
    async def challenges(self, ctx, challenge_title: Optional[str]):
        """LUHack challenges.

        Use the `challenges` command on its own to view the latest challenge or
        search for one.
        """
        if challenge_title is None:
            latest_challenge = (
                await Challenge.query.order_by(
                    Challenge.creation_date.desc(), Challenge.id.desc()
                )
                .where(sa.not_(Challenge.hidden))
                .gino.first()
            )

            if latest_challenge is None:
                await ctx.send("There are no challenges currently")
                return

            s = self.format_challenge(latest_challenge)
            await ctx.send(f"The latest challenge is: {s}")
            return

        challenge = await self.get_challenge(challenge_title)

        if challenge is None:
            await self.show_similar_challenges(
                ctx,
                challenge_title,
                "Challenge by that title not found, similar challenges are:",
            )
            return

        await ctx.send(self.format_challenge(challenge))

    @challenges.command(aliases=["bt"])
    async def by_tag(self, ctx, tag: str):
        await ctx.send(self.tag_url(tag))

    @challenges.command()
    async def stats(
        self,
        ctx,
        tag_condition: Optional[Literal["every", "any"]] = "every",
        season: Optional[int] = CURRENT_SEASON,
        *tags: str,
    ):
        """View the most and lest solved challenges.

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

        count = sa.func.count(CompletedChallenge.challenge_id).label("count")
        rank = sa.func.dense_rank().over(order_by=sa.desc("count")).label("rank")

        q_most = (
            db.select([Challenge.title, Challenge.points, count])
            .select_from(Challenge.outerjoin(CompletedChallenge))
            .where(tag_filter(tags))
            .where(sa.not_(Challenge.hidden))
            .where(CompletedChallenge.season == season)
            .group_by(Challenge.id)
            .alias("inner")
        )

        most = await (
            db.select([rank, q_most.c.title, q_most.c.count, q_most.c.points])
            .select_from(q_most)
            .limit(5)
            .order_by(sa.desc(q_most.c.count))
            .gino.load(
                (rank, q_most.c.title, ColumnLoader(q_most.c.count), q_most.c.points)
            )
            .all()
        )

        q_least = (
            db.select([Challenge.title, Challenge.points, count])
            .select_from(Challenge.outerjoin(CompletedChallenge))
            .where(tag_filter(tags))
            .where(sa.not_(Challenge.hidden))
            .where(CompletedChallenge.season == season)
            .group_by(Challenge.id)
            .alias("inner")
        )

        least = await (
            db.select([rank, q_least.c.title, q_least.c.count, q_least.c.points])
            .select_from(q_least)
            .order_by(sa.asc(q_least.c.count))
            .limit(5)
            .gino.load(
                (rank, q_least.c.title, ColumnLoader(q_least.c.count), q_least.c.points)
            )
            .all()
        )

        most_table = tabulate(
            most,
            headers=["Rank", "Challenge Title", "Solves", "Points"],
            tablefmt="github",
        )

        least_table = tabulate(
            least,
            headers=["Rank", "Challenge Title", "Solves", "Points"],
            tablefmt="github",
        )

        msg = textwrap.dedent(
            """
            ```md
            # Most Solved Challenges
            {most_table}

            # Least Solved Challenges
            {least_table}
            ```
            """
        ).format(most_table=most_table, least_table=least_table)

        await ctx.send(msg)

    @challenges.command(aliases=["top10"])
    async def leaderboard(
        self,
        ctx,
        tag_condition: Optional[Literal["every", "any"]] = "every",
        season: Optional[int] = CURRENT_SEASON,
        *tags: str,
    ):
        """View the leaderboard for completed challenges.

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

        score = sa.func.sum(Challenge.points).label("score")
        count = sa.func.count(Challenge.points).label("count")
        rank = sa.func.dense_rank().over(order_by=sa.desc("score")).label("rank")

        q = (
            db.select([User.discord_id, score, count])
            .select_from(User.join(CompletedChallenge).join(Challenge))
            .where(tag_filter(tags))
            .where(sa.not_(Challenge.hidden))
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

        await ctx.send(f"Scoreboard for season {season}: ```\n{table}\n```")

    @challenges.command()
    async def info(
        self,
        ctx,
        season: Optional[int] = CURRENT_SEASON,
    ):
        """Get info about your solved and unsolved challenges."""

        solved_challenges = (
            db.select([CompletedChallenge.challenge_id])
            .where(CompletedChallenge.discord_id == ctx.author.id)
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
            .where(sa.not_(Challenge.hidden))
            .where(CompletedChallenge.season == season)
            .group_by(User.discord_id)
            .cte("scores")
        )
        my_score = (
            db.select([sa.func.coalesce(scores_q.c.score, 0)])
            .select_from(scores_q)
            .where(scores_q.c.discord_id == ctx.author.id)
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
            Challenge info for {ctx.author} in season {season}:

            Solves: {count}
            Points: {points}
            Rank: {rank_value}
            Solved: `{solved_msg}`
            Unsolved: `{unsolved_msg}`
        """
        )

        await ctx.send(msg)

    @challenges.command(aliases=["solve", "submit"])
    async def claim(self, ctx, challenge: Optional[ChallengeName] = None, *, flag: str):
        """Claim a flag, make sure to use this in DMs."""
        warn_dm_message = ""

        flag = flag.strip()

        if ctx.guild:
            await ctx.message.delete()
            warn_dm_message = "\n\nP.S. Use this command in DMs next time."

        if challenge is None:
            # if this is a flag solve

            challenge = (
                await Challenge.query.where(Challenge.flag == flag)
                .where(sa.not_(Challenge.hidden))
                .gino.first()
            )

            if challenge is None:
                await ctx.send(
                    "That doesn't look to be a valid flag." + warn_dm_message
                )
                return

        elif challenge.answer != flag:
            # if this is an answer solve
            await ctx.send("That isn't the correct answer, sorry.")
            return

        if challenge.depreciated:
            msg = textwrap.dedent(
                """
                Congrats on completing the challenge!

                Unfortunately you can no longer score points for this challenge because
                a writeup has been released, or for other reasons.
                """
            )
            await ctx.send(msg)
            return

        already_claimed = await CompletedChallenge.query.where(
            (CompletedChallenge.discord_id == ctx.author.id)
            & (CompletedChallenge.challenge_id == challenge.id)
            & (CompletedChallenge.season == CURRENT_SEASON)
        ).gino.first()

        if already_claimed is not None:
            await ctx.send(
                "It looks like you've already claimed this flag." + warn_dm_message
            )
            return

        await CompletedChallenge.create(
            discord_id=ctx.author.id, challenge_id=challenge.id, season=CURRENT_SEASON
        )
        await ctx.send(
            f"Congrats, you've completed this challenge and have been awarded {challenge.points} points!"
            + warn_dm_message
        )

    @commands.check(is_admin)
    @challenges.command()
    async def admin(
        self,
        ctx,
        op: Literal["hide", "unhide", "depreciate", "undepreciate"],
        tag_condition: Optional[Literal["every", "any"]] = "every",
        *tags: str,
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

        await ctx.send(f"Updated {r} challenges")

    @commands.check(is_admin)
    @challenges.command()
    async def announce(
        self,
        ctx,
        op: Literal["avail", "depreciated"],
        tag_condition: Optional[Literal["every", "any"]] = "every",
        *tags: str,
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
            "avail": lambda c: (
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

        channel = ctx.bot.luhack_guild().get_channel(constants.challenge_log_channel_id)

        if channel is None:
            await ctx.send("Couldn't find challenge log channel?")
            return

        for challenge in challenges:
            title, desc, colour = data_fn(challenge)
            embed = discord.Embed(
                title=title,
                description=desc,
                color=colour,
                timestamp=datetime.utcnow(),
                url=str(self.challenge_url(challenge.slug)),
            )
            await channel.send(embed=embed)


def strip_prefix(s, pre):
    if s.startswith(pre):
        return s[len(pre) :]
    return s


def setup(bot):
    bot.add_cog(Challenges(bot))
