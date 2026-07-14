"""키워드 CRUD."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, Response

from app.csrf import verify_csrf
from app.flash import flash as _flash
from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import keyword_repo
from app.excel import ExcelColumn, xlsx_response

router = APIRouter(prefix="/keywords")

SOURCE_TYPES = ["NAVER_NEWS", "DAUM_NEWS", "GOOGLE_NEWS", "BAIDU_NEWS", "NAVER_STOCK", "DUCKDUCKGO_NEWS"]

# "최근 N일 합계" 컬럼 / 상세 페이지 공용 프리셋. 그 외 값이 들어오면 기본값으로 취급.
STATS_DAYS_CHOICES = (7, 14, 30)
DEFAULT_STATS_DAYS = 7

_EXPORT_COLUMNS = [
    ExcelColumn("id", "ID"),
    ExcelColumn("keyword", "키워드"),
    ExcelColumn("display_name", "표시 이름"),
    ExcelColumn("source_type", "소스"),
    ExcelColumn("priority", "우선순위"),
    ExcelColumn("interval_seconds", "주기(초)"),
    ExcelColumn("next_discover_at", "다음 수집"),
    ExcelColumn("enabled", "상태", formatter=lambda v: "활성" if v else "비활성"),
    ExcelColumn("disabled_reason", "비활성 사유"),
]


def _clean_stats_days(stats_days: int) -> int:
    return stats_days if stats_days in STATS_DAYS_CHOICES else DEFAULT_STATS_DAYS


@router.get("")
async def list_keywords(
    request: Request,
    source_type: str = "",
    enabled: str = "",
    search: str = "",
    sort: str = "",
    order: str = "asc",
    stats_days: int = Query(DEFAULT_STATS_DAYS),
):
    if order not in ("asc", "desc"):
        order = "asc"
    stats_days = _clean_stats_days(stats_days)
    stats_from_date = date.today() - timedelta(days=stats_days - 1)

    with get_engine().connect() as conn:
        keywords = keyword_repo.list_keywords(
            conn,
            source_type=source_type or None,
            enabled=enabled or None,
            search=search or None,
            sort_by=sort or None,
            sort_order=order,
            stats_from_date=stats_from_date,
        )
        counts = keyword_repo.get_source_type_counts(conn)

    flash = request.session.pop("flash", None)
    return templates.TemplateResponse("keywords/list.html", {
        "request": request,
        "active_page": "keywords",
        "keywords": keywords,
        "counts": counts,
        "source_types": SOURCE_TYPES,
        "filter_source": source_type,
        "filter_enabled": enabled,
        "search": search,
        "sort_by": sort,
        "sort_order": order,
        "stats_days": stats_days,
        "stats_days_choices": STATS_DAYS_CHOICES,
        "flash": flash,
    })


@router.get("/export.xlsx")
async def export_keywords(
    source_type: str = "",
    enabled: str = "",
    search: str = "",
    sort: str = "",
    order: str = "asc",
    stats_days: int = Query(DEFAULT_STATS_DAYS),
) -> Response:
    """현재 화면의 검색·필터·정렬 조건을 그대로 적용해 조회 결과를 엑셀로 내려받는다."""
    if order not in ("asc", "desc"):
        order = "asc"
    stats_days = _clean_stats_days(stats_days)
    stats_from_date = date.today() - timedelta(days=stats_days - 1)

    with get_engine().connect() as conn:
        keywords = keyword_repo.list_keywords(
            conn,
            source_type=source_type or None,
            enabled=enabled or None,
            search=search or None,
            sort_by=sort or None,
            sort_order=order,
            stats_from_date=stats_from_date,
        )
    export_columns = _EXPORT_COLUMNS + [
        ExcelColumn("total_collected", f"최근 {stats_days}일 수집 수"),
    ]
    return xlsx_response(keywords, export_columns, filename="키워드_관리", sheet_name="키워드")


@router.get("/{keyword_id}/stats")
async def keyword_stats(request: Request, keyword_id: int, days: int = Query(DEFAULT_STATS_DAYS)):
    """키워드 1개의 일자별 수집 URL 건수 — 목록의 "합계" 클릭 시 드릴다운."""
    days = _clean_stats_days(days)
    from_date = date.today() - timedelta(days=days - 1)

    with get_engine().connect() as conn:
        kw = keyword_repo.get_keyword(conn, keyword_id)
        if not kw:
            _flash(request, "키워드를 찾을 수 없습니다.", "danger")
            return RedirectResponse("/keywords", status_code=303)
        raw_counts = keyword_repo.get_daily_counts(conn, keyword_id, from_date)

    by_date = {r["collected_date"].isoformat(): r["cnt"] for r in raw_counts}
    daily = []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        d_iso = d.isoformat()
        daily.append({
            "date": d_iso,
            "label": d.strftime("%m/%d"),
            "count": int(by_date.get(d_iso, 0)),
        })

    return templates.TemplateResponse("keywords/stats.html", {
        "request": request,
        "active_page": "keywords",
        "kw": kw,
        "daily": daily,
        "days": days,
        "stats_days_choices": STATS_DAYS_CHOICES,
        "total": sum(d["count"] for d in daily),
    })


@router.get("/new")
async def new_keyword_form(request: Request):
    return templates.TemplateResponse("keywords/form.html", {
        "request": request,
        "active_page": "keywords",
        "source_types": SOURCE_TYPES,
        "kw": None,
    })


@router.post("/new", dependencies=[Depends(verify_csrf)])
async def create_keyword(
    request: Request,
    keyword: str = Form(...),
    source_type: str = Form(...),
    display_name: str = Form(""),
    priority: int = Form(0),
    interval_seconds: int = Form(86400),
):
    try:
        with get_engine().connect() as conn:
            keyword_repo.create_keyword(conn, keyword, source_type, display_name or None, priority, interval_seconds)
        _flash(request, f"키워드 '{keyword}' ({source_type}) 가 등록되었습니다.")
    except Exception as e:
        _flash(request, f"등록 실패: {e}", "danger")
    return RedirectResponse("/keywords", status_code=303)


@router.get("/{keyword_id}/edit")
async def edit_keyword_form(request: Request, keyword_id: int):
    with get_engine().connect() as conn:
        kw = keyword_repo.get_keyword(conn, keyword_id)
    if not kw:
        return RedirectResponse("/keywords", status_code=303)
    return templates.TemplateResponse("keywords/form.html", {
        "request": request,
        "active_page": "keywords",
        "source_types": SOURCE_TYPES,
        "kw": kw,
    })


@router.post("/{keyword_id}/edit", dependencies=[Depends(verify_csrf)])
async def update_keyword(
    request: Request,
    keyword_id: int,
    keyword: str = Form(...),
    display_name: str = Form(""),
    priority: int = Form(0),
    interval_seconds: int = Form(86400),
):
    try:
        with get_engine().connect() as conn:
            keyword_repo.update_keyword(conn, keyword_id, keyword, display_name or None, priority, interval_seconds)
        _flash(request, "키워드가 수정되었습니다.")
    except Exception as e:
        _flash(request, f"수정 실패: {e}", "danger")
    return RedirectResponse("/keywords", status_code=303)


@router.post("/{keyword_id}/toggle", dependencies=[Depends(verify_csrf)])
async def toggle_keyword(
    request: Request,
    keyword_id: int,
    enabled: str = Form(...),
    disabled_reason: str = Form(""),
):
    is_enabled = enabled == "true"
    with get_engine().connect() as conn:
        keyword_repo.toggle_enabled(conn, keyword_id, is_enabled, disabled_reason or None)
    action = "활성화" if is_enabled else "비활성화"
    _flash(request, f"키워드가 {action}되었습니다.")
    return RedirectResponse("/keywords", status_code=303)


@router.post("/{keyword_id}/trigger", dependencies=[Depends(verify_csrf)])
async def trigger_keyword(request: Request, keyword_id: int):
    with get_engine().connect() as conn:
        kw = keyword_repo.get_keyword(conn, keyword_id)
        keyword_repo.trigger_now(conn, keyword_id)
    name = kw["keyword"] if kw else str(keyword_id)
    _flash(request, f"'{name}' 즉시 수집 예약 완료.")
    return RedirectResponse("/keywords", status_code=303)
