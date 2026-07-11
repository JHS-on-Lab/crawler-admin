"""플래시 메시지 — 세션에 담아뒀다가 다음 페이지 렌더링 시 1회 표시한다.

urls.py/keywords.py/domains.py 에 동일한 함수가 각각 복붙돼 있던 것을 하나로 통일.
"""

from __future__ import annotations

from fastapi import Request


def flash(request: Request, msg: str, level: str = "success") -> None:
    request.session["flash"] = {"msg": msg, "level": level}
