import typing
import functools
from typing import Callable, List

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class HeaderMiddleware:
    def __init__(self, app: ASGIApp, headers: typing.Dict[str, str]):
        self.app = app
        self.__headers = headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        headers = Headers(scope=scope)

        await self.response(scope, receive, send, request_headers=headers)

    async def response(
        self, scope: Scope, receive: Receive, send: Send, request_headers: Headers
    ):
        send = functools.partial(self.send, send=send, request_headers=request_headers)
        await self.app(scope, receive, send)

    async def send(self, message: Message, send: Send, request_headers: Headers):
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers.update(self.__headers)

        await send(message)


class BlockerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, checks: List[Callable[[Headers], bool]], fail: Response) -> None:
        super().__init__(app)
        self.__checks = checks
        self.__fail = fail

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        for f in self.__checks:
            if not f(request.headers):
                return self.__fail
        return await call_next(request)

class WebSecMiddleware(HeaderMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(
            app,
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
            },
        )


class HSTSMiddleware(HeaderMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app, {"Strict-Transport-Security": "max-age=63072000"})


class CSPMiddleware(HeaderMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        default_src: typing.Sequence[str] = ("'none'",),
        script_src: typing.Sequence[str] = ("'self'",),
        connect_src: typing.Sequence[str] = ("'self'",),
        img_src: typing.Sequence[str] = ("*", "'self'", "data:"),
        style_src: typing.Sequence[str] = ("'self'",),
    ):
        ds = "default-src " + " ".join(default_src)
        scs = "script-src " + " ".join(script_src)
        cs = "connect-src " + " ".join(connect_src)
        is_ = "img-src " + " ".join(img_src)
        sts = "style-src " + " ".join(style_src)
        header_content = ";".join((ds, scs, cs, is_, sts))

        super().__init__(app, {"Content-Security-Policy": header_content})
