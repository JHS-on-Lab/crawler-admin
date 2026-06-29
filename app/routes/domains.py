"""도메인 규칙 조회 및 수정."""

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import domain_repo

router = APIRouter(prefix="/domains")


def _flash(request: Request, msg: str, level: str = "success") -> None:
    request.session["flash"] = {"msg": msg, "level": level}


@router.get("")
async def list_domains(
    request: Request,
    search: str = "",
    rules_filter: str = "",
    sort: str = "",
    order: str = "asc",
):
    if order not in ("asc", "desc"):
        order = "asc"
    with get_engine().connect() as conn:
        domains = domain_repo.list_domains(
            conn,
            search=search or None,
            rules_filter=rules_filter or None,
            sort_by=sort or None,
            sort_order=order,
        )

    flash = request.session.pop("flash", None)
    return templates.TemplateResponse("domains/list.html", {
        "request": request,
        "active_page": "domains",
        "domains": domains,
        "search": search,
        "rules_filter": rules_filter,
        "sort_by": sort,
        "sort_order": order,
        "flash": flash,
    })


@router.post("/{host:path}/toggle-rules")
async def toggle_rules(request: Request, host: str):
    with get_engine().connect() as conn:
        domain = domain_repo.get_domain(conn, host)
        if domain:
            new_state = not domain["rules_enabled"]
            domain_repo.toggle_rules_enabled(conn, host, new_state)
            action = "활성화" if new_state else "비활성화"
            _flash(request, f"{host} 규칙을 {action}했습니다.")
    return RedirectResponse("/domains", status_code=303)


@router.post("/{host:path}/clear-cooldown")
async def clear_cooldown(request: Request, host: str):
    with get_engine().connect() as conn:
        domain_repo.clear_cooldown(conn, host)
    _flash(request, f"{host} 쿨다운을 해제했습니다.")
    return RedirectResponse("/domains", status_code=303)


@router.post("/{host:path}/edit-rules")
async def edit_rules(
    request: Request,
    host: str,
    rules_json: str = Form(...),
    rules_enabled: str = Form("false"),
):
    try:
        with get_engine().connect() as conn:
            domain_repo.update_rules(conn, host, rules_json, rules_enabled == "true")
        _flash(request, f"{host} 규칙이 저장되었습니다.")
    except json.JSONDecodeError:
        _flash(request, "JSON 형식이 올바르지 않습니다.", "danger")
    except Exception as e:
        _flash(request, f"저장 실패: {e}", "danger")
    return RedirectResponse("/domains", status_code=303)
