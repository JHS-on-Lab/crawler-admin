"""플래시 메시지 — 세션에 담아뒀다가 다음 페이지 렌더링 시 1회 표시한다."""

from __future__ import annotations

from fastapi import Request


def flash(request: Request, msg: str, level: str = "success") -> None:
    request.session["flash"] = {"msg": msg, "level": level}


def flash_context_processor(request: Request) -> dict:
    """Jinja2Templates(context_processors=[...]) 에 연결 — 모든 템플릿 렌더링에
    flash 를 자동으로 주입한다(app.csrf.csrf_context_processor 와 동일 패턴).

    라우트가 각자 request.session.pop("flash", None) 을 안 부르면, 그 라우트를
    거치는 동안 플래시가 세션에 남아있다가 나중에 방문한 다른 페이지에서 뜨는
    문제가 생긴다 — 모든 렌더링에서 매번 pop 하면 이 문제 자체가 없어진다."""
    return {"flash": request.session.pop("flash", None)}
