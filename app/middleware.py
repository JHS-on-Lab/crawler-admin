"""인증 미들웨어 — 비로그인 요청을 /login 으로 리다이렉트."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

_PUBLIC = {"/login", "/favicon.ico"}


class RequireLoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path not in _PUBLIC:
            if not request.session.get("authenticated"):
                return RedirectResponse("/login", status_code=303)
        return await call_next(request)
