import typing
import functools

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class CSPMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        default_src: typing.Sequence[str] = ("'none'",),
        script_src: typing.Sequence[str] = ("'self'",),
        connect_src: typing.Sequence[str] = ("'self'",),
        img_src: typing.Sequence[str] = ("*",),
        style_src: typing.Sequence[str] = ("'self'",),
    ):
        self.app = app
        ds = "default-src " + " ".join(default_src)
        scs = "script-src " + " ".join(script_src)
        cs = "connect-src " + " ".join(connect_src)
        is_ = "img-src " + " ".join(img_src)
        sts = "style-src " + " ".join(style_src)
        header_content = ";".join((ds, scs, cs, is_, sts))

        self.headers = {"Content-Security-Policy": header_content}

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
        headers.update(self.headers)

        await send(message)
