"""도메인 규칙 조회 및 수정."""

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import domain_repo
from app.excel import ExcelColumn, xlsx_response

router = APIRouter(prefix="/domains")

_EXPORT_COLUMNS = [
    ExcelColumn("host", "도메인"),
    ExcelColumn("excluded", "차단 여부", formatter=lambda v: "차단" if v else "정상"),
    ExcelColumn("render_mode", "렌더 모드"),
    ExcelColumn("rules_enabled", "규칙 활성화", formatter=lambda v: "활성" if v else "비활성"),
    ExcelColumn("crawl_delay_ms", "지연(ms)"),
    ExcelColumn("success_rate", "성공률(%)",
                formatter=lambda v: round(v * 100, 1) if v is not None else None),
    ExcelColumn("recent_fail_count", "실패 수"),
    ExcelColumn("cooldown_until", "쿨다운 종료"),
    ExcelColumn("updated_by", "수정자"),
    ExcelColumn("updated_at", "수정일시"),
    ExcelColumn("rules_json", "추출 규칙(JSON)",
                formatter=lambda v: json.dumps(v, ensure_ascii=False) if v else None,
                width=50),
]


def _flash(request: Request, msg: str, level: str = "success") -> None:
    request.session["flash"] = {"msg": msg, "level": level}


@router.get("")
async def list_domains(
    request: Request,
    search: str = "",
    rules_filter: str = "",
    excluded_filter: str = "",
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
            excluded_filter=excluded_filter or None,
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
        "excluded_filter": excluded_filter,
        "sort_by": sort,
        "sort_order": order,
        "flash": flash,
    })


@router.get("/export.xlsx")
async def export_domains(
    search: str = "",
    rules_filter: str = "",
    excluded_filter: str = "",
    sort: str = "",
    order: str = "asc",
) -> Response:
    """현재 화면의 검색·필터·정렬 조건을 그대로 적용해 조회 결과를 엑셀로 내려받는다."""
    if order not in ("asc", "desc"):
        order = "asc"
    with get_engine().connect() as conn:
        domains = domain_repo.list_domains(
            conn,
            search=search or None,
            rules_filter=rules_filter or None,
            excluded_filter=excluded_filter or None,
            sort_by=sort or None,
            sort_order=order,
        )
    return xlsx_response(domains, _EXPORT_COLUMNS, filename="도메인_규칙", sheet_name="도메인 규칙")


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


@router.post("/{host:path}/toggle-excluded")
async def toggle_excluded(request: Request, host: str):
    with get_engine().connect() as conn:
        domain = domain_repo.get_domain(conn, host)
        if domain:
            new_state = not domain["excluded"]
            domain_repo.toggle_excluded(conn, host, new_state)
            action = "차단" if new_state else "차단 해제"
            _flash(request, f"{host}을(를) {action}했습니다.")
    return RedirectResponse("/domains", status_code=303)


@router.post("/block")
async def block_domain(request: Request, host: str = Form(...)):
    host = host.strip().lower()
    with get_engine().connect() as conn:
        domain_repo.block_domain(conn, host)
    _flash(request, f"{host}을(를) 차단했습니다.")
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
