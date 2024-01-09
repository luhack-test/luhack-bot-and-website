import logging
from pathlib import Path
from typing import List, Tuple

from luhack_bot.db.helpers import init_db
from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.config import Config
from starlette.endpoints import HTTPEndpoint
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import Response
from starlette.responses import RedirectResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from luhack_site import settings
from luhack_site.authorization import TokenAuthBackend, can_edit
from luhack_site.challenges import router as challenge_router
from luhack_site.images import router as images_router
from luhack_site.middleware import (
    BlockerMiddleware,
    CSPMiddleware,
    HSTSMiddleware,
    WebSecMiddleware,
)
from luhack_site.oauth import router as oauth_router
from luhack_site.templater import templates
from luhack_site.writeups import router as writeups_router
from luhack_site.sessions import SessionMiddleware

log: logging.Logger = logging.getLogger("luhack_site")
log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)


root_dir = Path(__file__).parent

app = Starlette(
    routes=[
        Mount("/writeups", app=writeups_router),
        Mount("/images", app=images_router),
        Mount("/challenges", app=challenge_router),
        Mount("/oauth", app=oauth_router),
    ]
)

app.add_middleware(HSTSMiddleware)
app.add_middleware(WebSecMiddleware)
app.add_middleware(
    CSPMiddleware,
    script_src=(
        "'self'",
        "'sha256-gUOO8cVce0Qg1lxrPgv8NIo//GS1rTLlhFvALeuQ3kg='",
    ),
    connect_src=("'self'", "www.google-analytics.com"),
    default_src=(
        "'self'",
        "cdnjs.cloudflare.com",
        "unpkg.com",
        "fonts.bunny.net"
    ),
    style_src=("'self'", "cdnjs.cloudflare.com", "unpkg.com", "fonts.bunny.net"),
)
app.add_middleware(AuthenticationMiddleware, backend=TokenAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=settings.TOKEN_SECRET)
app.add_middleware(
    BlockerMiddleware,
    checks=[lambda h: "httrack" not in h["user-agent"].lower()],
    fail=Response("who thought this was a good idea?", 418),
)


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
async def index(_:HTTPConnection):
    return RedirectResponse(url="https://luhack.uk", status_code=301)

@app.route("/plzauth")
async def need_auth(request: HTTPConnection):
    return templates.TemplateResponse("plzauth.j2", {"request": request})


@app.route("/baka")
async def not_admin(request: HTTPConnection):
    return templates.TemplateResponse("baka.j2", {"request": request})


@app.route("/fresher_challenge")
async def view_challenge(request: HTTPConnection):
    return templates.TemplateResponse(
        "fresher_challenge/challenge.j2", {"request": request}
    )


@app.route("/stegoBoi")
async def view_stego(request: HTTPConnection):
    return templates.TemplateResponse(
        "fresher_challenge/stegoboi.j2", {"request": request}
    )


@app.route("/robots.txt")
async def view_robots(request: HTTPConnection):
    return await statics.get_response("robots.txt", request.scope)


@app.route("/sitemap.xml")
async def view_sitemap(request: HTTPConnection):
    return await statics.get_response("sitemap.xml", request.scope)


@app.on_event("startup")
async def startup():
    await init_db()
