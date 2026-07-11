"""로그인 / 로그아웃."""

import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import config
from app.csrf import verify_csrf
from app.tmpl import templates

router = APIRouter()

# 로그인 시도 제한 — 클라이언트 IP 별로 실패 횟수를 기억한다.
# 단일 프로세스 내 인메모리 상태라 재시작하면 초기화되지만, 관리자 계정 하나만
# 있는 내부 도구 규모에서는 별도 저장소 없이 이 정도로 충분하다.
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_SECONDS = 900  # 15분
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_locked_out(key: str) -> bool:
    now = time.monotonic()
    _failed_attempts[key] = [t for t in _failed_attempts[key] if now - t < _LOCKOUT_SECONDS]
    return len(_failed_attempts[key]) >= _MAX_LOGIN_ATTEMPTS


def _record_failure(key: str) -> None:
    _failed_attempts[key].append(time.monotonic())


def _clear_failures(key: str) -> None:
    _failed_attempts.pop(key, None)


def _safe_equals(a: str, b: str) -> bool:
    """타이밍 공격 방지를 위한 상수 시간 비교. compare_digest 는 ASCII str 만
    받으므로 유니코드(한글 등) 자격증명도 안전하게 비교하도록 utf-8 로 인코딩한다."""
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@router.get("/login")
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", dependencies=[Depends(verify_csrf)])
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    key = _client_key(request)

    if _is_locked_out(key):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": f"로그인 시도가 너무 많습니다. {_LOCKOUT_SECONDS // 60}분 후 다시 시도하세요.",
            },
            status_code=429,
        )

    if _safe_equals(username, config.ADMIN_USER) and _safe_equals(password, config.ADMIN_PASSWORD):
        _clear_failures(key)
        request.session["authenticated"] = True
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)

    _record_failure(key)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
