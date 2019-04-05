import flask_pure
import quart
from quart import (
    Quart,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from luhack_bot.db.helpers import init_db
from luhack_bot.db.models import User, Writeup, db

app = Quart(__name__)

# just a bit of monkey patching
flask_pure.Blueprint = quart.Blueprint
flask_pure.Markup = quart.Markup
flask_pure.current_app = quart.current_app
flask_pure.url_for = quart.url_for

flask_pure.Pure(app)


async def get_db():
    if hasattr(g, "db"):
        return g.db

    await init_db()
    g.db = db


@app.route("/<title>")
async def view(title: str):
    db = await get_db()
    writeup = await Writeup.query.where(Writeup.title == title).gino.first()

    if writeup is None:
        abort(404, "Writeup not found")

    return await render_template("writeup.html", writeup=writeup)
