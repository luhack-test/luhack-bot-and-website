import random
import ast
import textwrap

import discord
from discord.ext import commands

from luhack_bot.utils.checks import is_admin


coc_urls = [
    "https://cdn.discordapp.com/attachments/631618075254325257/632260899939287051/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/632258249579561012/2Q.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/632257793201799198/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/632257107076579331/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/632246273466040321/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/632183877477203978/IMG_20191010_231703.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/632183673269125120/download.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/632182097003413505/IMG_20191010_232642.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/631996568467406848/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/631987156969193485/unknown.png",
    "https://cdn.discordapp.com/attachments/631618075254325257/631984684905267200/IMG_20191010_234106.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/631984019537395723/IMG_20191010_233823.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/631982101289369616/IMG_20191010_233104.jpg",
    "https://cdn.discordapp.com/attachments/631618075254325257/631980398099824691/IMG_20191010_232415.jpg",
]


def insert_returns(body):
    # insert return stmt if the last expression is a expression statement
    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])

    # for if statements, we insert returns into the body and the orelse
    if isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)

    # for with blocks, again we insert returns into the body
    if isinstance(body[-1], ast.With):
        insert_returns(body[-1].body)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return is_admin(ctx)

    @commands.command()
    async def coc(self, ctx):
        """!!!CoC Violation!!!"""
        img = random.choice(coc_urls)
        msg = f"!!!CoC Violation Detected!!!!\n{img}"
        await ctx.send(msg)

    @commands.command()
    async def reload(self, ctx, module):
        try:
            if module in self.bot.extensions:
                self.bot.reload_extension(module)
            else:
                self.bot.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f"Failed to (re)load {module}: {e}")
        else:
            await ctx.send(f"(Re)Loaded {module}")

    @commands.command(name="eval")
    async def eval_fn(self, ctx, *, cmd):
        """Evaluates input.
        Input is interpreted as newline seperated statements.
        If the last statement is an expression, that is the return value.
        Usable globals:
        - `bot`: the bot instance
        - `discord`: the discord module
        - `commands`: the discord.ext.commands module
        - `ctx`: the invokation context
        - `__import__`: the builtin `__import__` function
        Such that `>eval 1 + 1` gives `2` as the result.
        The following invokation will cause the bot to send the text '9'
        to the channel of invokation and return '3' as the result of evaluating
        >eval ```
        a = 1 + 2
        b = a * 2
        await ctx.send(a + b)
        a
        ```
        """
        fn_name = "_eval_expr"

        cmd = cmd.strip("` ")

        # add a layer of indentation
        cmd = textwrap.indent(cmd, " " * 2)

        # wrap in async def body
        body = f"async def {fn_name}():\n{cmd}"

        parsed = ast.parse(body)
        body = parsed.body[0].body

        insert_returns(body)

        env = {
            "bot": ctx.bot,
            "discord": discord,
            "commands": commands,
            "ctx": ctx,
            "__import__": __import__,
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)

        result = await eval(f"{fn_name}()", env)
        await ctx.send(result)

def setup(bot):
    bot.add_cog(Admin(bot))
