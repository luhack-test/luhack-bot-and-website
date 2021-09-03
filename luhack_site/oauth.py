import logging

from authlib.integrations.starlette_client import OAuth
from starlette.requests import HTTPConnection
from starlette.responses import RedirectResponse
from starlette.routing import Router

from luhack_site import settings

log: logging.Logger = logging.getLogger(__name__)

router = Router()

DISCORD_API_BASE = "https://discord.com/api"
DISCORD_OAUTH_URL_BASE = DISCORD_API_BASE + "/oauth2"
DISCORD_OAUTH_URL_AUTHORIZE = DISCORD_OAUTH_URL_BASE + "/authorize"
DISCORD_OAUTH_URL_TOKEN = DISCORD_OAUTH_URL_BASE + "/token"
DISCORD_OAUTH_URL_TOKEN_REVOKE = DISCORD_OAUTH_URL_BASE + "/token/revoke"

oauth = OAuth(settings.config)
oauth.register(
    name="discord",
    authorization_endpoint=DISCORD_OAUTH_URL_AUTHORIZE,
    token_endpoint=DISCORD_OAUTH_URL_TOKEN,
    revocation_endpoint=DISCORD_OAUTH_URL_TOKEN_REVOKE,
    client_kwargs={"scope": "identify"},
)


@router.route("/")
async def sign_in(request: HTTPConnection):
    redirect_uri = request.url_for("auth_cb")
    return await oauth.discord.authorize_redirect(request, redirect_uri)


@router.route("/auth")
async def auth_cb(request: HTTPConnection):
    token = await oauth.discord.authorize_access_token(request)
    resp = await oauth.discord.get(DISCORD_API_BASE + "/users/@me", token=token)
    user = resp.json()
    log.info(
        "User %s#%s (%s) completed oauth",
        user["username"],
        user["discriminator"],
        user["id"],
    )
    request.session["discord_id"] = int(user["id"])
    return RedirectResponse(url="/")


@router.route("/logout")
async def logout(request: HTTPConnection):
    request.session.pop("discord_id", None)
    return RedirectResponse(url="/")
