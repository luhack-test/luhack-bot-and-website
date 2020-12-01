from pathlib import Path
from typing import List, Tuple

from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.authentication import requires
from starlette.endpoints import HTTPEndpoint
from starlette.routing import Mount
from starlette.requests import HTTPConnection
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.config import Config

from luhack_site.authorization import TokenAuthBackend, can_edit
from luhack_site.templater import templates
from luhack_site.writeups import router as writeups_router
from luhack_site.images import router as images_router
from luhack_site.blog import router as blog_router
from luhack_site.oauth import router as oauth_router
from luhack_site.challenges import router as challenge_router
from luhack_site.middleware import BlockerMiddleware, CSPMiddleware, HSTSMiddleware, WebSecMiddleware
from luhack_site import settings

from luhack_bot.db.helpers import init_db


root_dir = Path(__file__).parent

app = Starlette(
    routes=[
        Mount("/writeups", app=writeups_router),
        Mount("/images", app=images_router),
        Mount("/blog", app=blog_router),
        Mount("/challenges", app=challenge_router),
        Mount("/oauth", app=oauth_router),
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
app.add_middleware(SessionMiddleware, secret_key=settings.TOKEN_SECRET)
app.add_middleware(BlockerMiddleware, checks=[lambda h: "httrack" not in h["user-agent"].lower()], fail=Response("who thought this was a good idea?", 418))

class CacheHeaderStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers.append("Cache-Control", "public")
        r.headers.append("Cache-Control", "must-revalidate")
        r.headers.append("Cache-Control", "max-age=360")

        return r

statics = CacheHeaderStaticFiles(directory=str(root_dir / "static"))
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


@app.route("/fresher_challenge")
async def view_challenge(request: HTTPConnection):
    return templates.TemplateResponse("fresher_challenge/challenge.j2", {"request": request})


@app.route("/stegoBoi")
async def view_stego(request: HTTPConnection):
    return templates.TemplateResponse("fresher_challenge/stegoboi.j2", {"request": request})


@app.on_event("startup")
async def startup():
    await init_db()
