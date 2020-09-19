import logging
import textwrap
from typing import List, Tuple, TypeVar
from typing import Optional
from tabulate import tabulate

import discord
from discord.ext import commands
import sqlalchemy as sa
from sqlalchemy_searchable import search as pg_search
from gino.loader import ColumnLoader

from luhack_bot import constants
from luhack_bot.db.models import User, Challenge, CompletedChallenge, db
from luhack_bot.utils.checks import is_authed

logger = logging.getLogger(__name__)


T = TypeVar("T")

def split_on(l: List[Tuple[T, bool]]) -> Tuple[List[T], List[T]]:
    a, b = [], []
    for v, k in l:
        (a if k else b).append(v)
    return a, b


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await is_authed(ctx)

    @staticmethod
    def challenge_url(slug):
        return constants.challenges_base_url / "view" / slug

    async def get_challenge(self, title: str) -> Optional[Challenge]:
        return await Challenge.query.where(Challenge.title == title).gino.first()

    async def search_challenges(self, search: str) -> List[Challenge]:
        """Search for challenges, return top 3 matching."""
        return await pg_search(Challenge.query, search, sort=True).limit(3).gino.all()

    def format_challenge(self, challenge: Challenge) -> str:
        return f'"{challenge.title}" ({self.challenge_url(challenge.slug)})'

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

    @commands.group(aliases=["challenge"], invoke_without_command=True)
    async def challenges(self, ctx, challenge_title: Optional[str]):
        if challenge_title is None:
            latest_challenge = await Challenge.query.order_by(
                Challenge.id.desc()
            ).gino.first()

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

    @challenges.command()
    async def add_debug(self, ctx, title: str, content: str, flag: str):
        challenge = await Challenge.create_auto(
            title=title,
            content=content,
            flag=flag,
            points=10,
        )

        await ctx.send(self.format_challenge(challenge))

    @challenges.command(aliases=["top10"])
    async def leaderboard(self, ctx):
        """View the leaderboard for completed challenges."""

        score = sa.func.sum(Challenge.points).label("score")
        count = sa.func.count(Challenge.points).label("count")
        rank = sa.func.rank().over(order_by=sa.desc("score")).label("rank")

        q = (
            db.select([User.discord_id, score, count])
            .select_from(User.join(CompletedChallenge).join(Challenge))
            .group_by(User.discord_id)
            .order_by(sa.desc("score"))
            .alias("inner")
        )

        scores = await (
            db.select([q.c.discord_id, q.c.score, q.c.count, rank])
            .select_from(q)
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

        await ctx.send(f"```md\n{table}\n```")

    @challenges.command()
    async def info(self, ctx):
        """Get info about your solved and unsolved challenges."""

        solved_challenges = (
            db.select([CompletedChallenge.challenge_id])
            .where(CompletedChallenge.discord_id == ctx.author.id)
            .cte("solved_challenges")
        )

        solved = (
            sa.exists()
            .where(solved_challenges.c.challenge_id == Challenge.id)
            .label("solved")
        )

        info = await (
            db.select([Challenge, solved])
            .gino.load((Challenge, ColumnLoader(solved)))
            .all()
        )

        solved, unsolved = split_on(info)

        points = sum(c.points for c in solved)
        count = len(solved)

        solved_msg = ", ".join(c.title for c in solved) or "No solves"
        unsolved_msg = ", ".join(c.title for c in unsolved) or "All solved"

        msg = textwrap.dedent(f"""
            Challenge info for {ctx.author}:

            Solves: {count}
            Points: {points}
            Solved: `{solved_msg}`
            Unsolved: `{unsolved_msg}`
        """)

        await ctx.send(msg)

    @challenges.command(aliases=["solve"])
    async def claim(self, ctx, flag: str):
        """Claim a flag, make sure to use this in DMs."""
        warn_dm_message = ""

        if ctx.guild:
            await ctx.message.delete()
            warn_dm_message = "\n\nP.S. Use this command in DMs next time."

        challenge = await Challenge.query.where(Challenge.flag == flag).gino.first()

        if challenge is None:
            await ctx.send("That doesn't look to be a valid flag." + warn_dm_message)
            return

        already_claimed = await CompletedChallenge.query.where(
            (CompletedChallenge.discord_id == ctx.author.id)
            & (CompletedChallenge.challenge_id == challenge.id)
        ).gino.first()

        if already_claimed is not None:
            await ctx.send(
                "It looks like you've already claimed this flag." + warn_dm_message
            )
            return

        await CompletedChallenge.create(
            discord_id=ctx.author.id, challenge_id=challenge.id
        )
        await ctx.send(
            f"Congrats, you've completed this challenge and have been awarded {challenge.points} points!"
            + warn_dm_message
        )


def setup(bot):
    bot.add_cog(Challenges(bot))
