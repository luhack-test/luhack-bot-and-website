from os import getenv
from pathlib import Path

from dotenv import load_dotenv

from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.staticfiles import StaticFiles
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Mount
from starlette.responses import PlainTextResponse
from starlette.templating import Jinja2Templates

from writeups_site.middleware import TokenAuthBackend
from writeups_site.markdown import markdown
from luhack_bot.db.helpers import init_db
from luhack_bot.db.models import User, Writeup, db

root_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(root_dir / "templates"))

load_dotenv(root_dir.parent)

app = Starlette(debug=True)

app.add_middleware(AuthenticationMiddleware, backend=TokenAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=getenv("TOKEN_SECRET"))

statics = StaticFiles(directory=str(root_dir / "static"))
app.mount("/static", statics, name="static")

def abort(status: int, reason: str = ""):
    return PlainTextResponse(reason, status)

# TODO: tags, search

@app.on_event("startup")
async def startup():
    await init_db()


@app.route("/")
async def index(request: HTTPConnection):
    return templates.TemplateResponse("base.j2", {"request": request})


@app.route("/{title}")
async def view(request: HTTPConnection):
    title = request.path_params["title"]

    writeup = await Writeup.load(author=User).where(Writeup.title == title).gino.first()

    if writeup is None:
        return abort(404, "Writeup not found")

    rendered = markdown(writeup.content)

    return templates.TemplateResponse(
        "writeup.j2", {"writeup": writeup, "request": request, "rendered": rendered}
    )


@app.route("/delete/{id:int}")
@requires("authenticated")
async def delete(request: HTTPConnection):
    id = request.path_params["id"]

    writeup = await Writeup.get(id)

    if writeup is None:
        return abort(404, "Writeup not found")
    
    if not request.user.is_admin and writeup.author_id != request.user.discord_id:
        return abort(400)
   
    await Writeup.delete.where(Writeup.id == id).gino.status()
