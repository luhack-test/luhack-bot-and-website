from os import getenv
from pathlib import Path
from typing import List, Tuple

from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.routing import Mount
from starlette.requests import HTTPConnection
from starlette.staticfiles import StaticFiles

from luhack_site import load_env
from luhack_site.authorization import TokenAuthBackend, can_edit
from luhack_site.templater import templates
from luhack_site.writeups import router as writeups_router
from luhack_site.images import router as images_router
from luhack_site.blog import router as blog_router
from luhack_site.middleware import CSPMiddleware, HSTSMiddleware, WebSecMiddleware

from luhack_bot.db.helpers import init_db


root_dir = Path(__file__).parent

app = Starlette(
    routes=[
        Mount("/writeups", app=writeups_router),
        Mount("/images", app=images_router),
        Mount("/blog", app=blog_router),
    ]
)

app.add_middleware(HSTSMiddleware)
app.add_middleware(WebSecMiddleware)
app.add_middleware(
    CSPMiddleware,
    default_src=(
        "'self'",
        "use.fontawesome.com",
        "unpkg.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    ),
    style_src=("'self'", "use.fontawesome.com", "unpkg.com", "fonts.googleapis.com"),
)
app.add_middleware(AuthenticationMiddleware, backend=TokenAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=getenv("TOKEN_SECRET"))

statics = StaticFiles(directory=str(root_dir / "static"))
app.mount("/static", statics, name="static")


templates.env.globals.update(can_edit=can_edit)


@app.route("/")
async def index(request: HTTPConnection):
    return templates.TemplateResponse("index.j2", {"request": request})


@app.route("/plzauth")
async def need_auth(request: HTTPConnection):
    return templates.TemplateResponse("plzauth.j2", {"request": request})


@app.route("/baka")
async def not_admin(request: HTTPConnection):
    return templates.TemplateResponse("baka.j2", {"request": request})


@app.route("/sign_out")
async def sign_out(request: HTTPConnection):
    request.session.pop("token", None)

    return RedirectResponse(url=request.url_for("index"))


@app.route("/challenge")
async def view_challenge(request: HTTPConnection):
    return templates.TemplateResponse("challenge/challenge.j2", {"request": request})


@app.route("/stegoBoi")
async def view_stego(request: HTTPConnection):
    return templates.TemplateResponse("challenge/stegoboi.j2", {"request": request})


@app.on_event("startup")
async def startup():
    await init_db()
