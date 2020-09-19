from starlette.responses import PlainTextResponse, RedirectResponse

def redirect_response(*args, **kwargs):
    kwargs.setdefault("status_code", 303)
    return RedirectResponse(*args, **kwargs)

def abort(status: int, reason: str = ""):
    return PlainTextResponse(reason, status)
