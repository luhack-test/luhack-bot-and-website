from starlette.responses import PlainTextResponse

def abort(status: int, reason: str = ""):
    return PlainTextResponse(reason, status)
