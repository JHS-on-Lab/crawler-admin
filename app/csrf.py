"""CSRF 보호 — synchronizer token 패턴.

세션마다 랜덤 토큰을 한 번 발급해 모든 폼에 hidden input 으로 심어두고,
state-changing POST 마다 제출된 값이 세션 토큰과 일치하는지 확인한다.
불일치/누락이면 403.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    """세션의 CSRF 토큰을 반환한다. 없으면 새로 발급해 세션에 저장한다."""
    token = request.session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[_SESSION_KEY] = token
    return token


def csrf_context_processor(request: Request) -> dict:
    """Jinja2Templates(context_processors=[...]) 에 연결 — 모든 템플릿 렌더링에
    csrf_token 을 자동으로 주입해, 각 라우트가 매번 context 에 넣지 않아도 된다."""
    return {"csrf_token": get_csrf_token(request)}


async def verify_csrf(request: Request) -> None:
    """state-changing POST 라우트에 Depends(verify_csrf) 로 연결한다.

    request.form() 은 Starlette 이 내부적으로 캐싱하므로, 라우트 자체의
    Form(...) 파라미터 파싱과 별개로 여기서 한 번 더 호출해도 안전하다.
    """
    form = await request.form()
    submitted = form.get(_SESSION_KEY, "")
    expected = request.session.get(_SESSION_KEY)
    if not expected or not isinstance(submitted, str) or not secrets.compare_digest(submitted, expected):
        raise HTTPException(
            status_code=403,
            detail="CSRF 토큰이 유효하지 않습니다. 페이지를 새로고침한 뒤 다시 시도하세요.",
        )
