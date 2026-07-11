"""URL 큐 조회 및 재투입."""

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse

from app.csrf import verify_csrf
from app.flash import flash as _flash
from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import crawl_url_repo

router = APIRouter(prefix="/urls")

SOURCE_TYPES = ["NAVER_NEWS", "DAUM_NEWS", "GOOGLE_NEWS", "BAIDU_NEWS", "NAVER_STOCK", "DUCKDUCKGO_NEWS", "SOLR_RESCRAPE"]
# crawl_url_repo.FAIL_STATUSES 와 별도로 여기 목록을 두면 나중에 어긋날 수 있어
# 하나의 정의를 그대로 가져다 쓴다.
FAIL_STATUSES = list(crawl_url_repo.FAIL_STATUSES)


@router.get("")
async def list_urls(
    request: Request,
    status: str = "",
    source_type: str = "",
    host: str = "",
    page: int = Query(1, ge=1),
):
    with get_engine().connect() as conn:
        summary = crawl_url_repo.get_status_summary(conn)
        rows, total = crawl_url_repo.list_failed_urls(
            conn,
            status=status or None,
            source_type=source_type or None,
            host=host or None,
            page=page,
        )

    status_map = {row["status"]: row["cnt"] for row in summary}
    total_pages = (total + crawl_url_repo.PAGE_SIZE - 1) // crawl_url_repo.PAGE_SIZE
    flash = request.session.pop("flash", None)

    return templates.TemplateResponse("urls/list.html", {
        "request": request,
        "active_page": "urls",
        "status_map": status_map,
        "rows": rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "source_types": SOURCE_TYPES,
        "fail_statuses": FAIL_STATUSES,
        "filter_status": status,
        "filter_source": source_type,
        "filter_host": host,
        "flash": flash,
    })


@router.post("/{url_id}/reinject", dependencies=[Depends(verify_csrf)])
async def reinject(request: Request, url_id: int):
    with get_engine().connect() as conn:
        ok = crawl_url_repo.reinject(conn, url_id)
    if ok:
        _flash(request, "URL을 재투입했습니다.")
    else:
        _flash(request, "재투입 대상이 아닙니다 (이미 처리 중이거나 완료된 URL일 수 있습니다).", level="danger")
    return RedirectResponse("/urls", status_code=303)


@router.post("/reinject-bulk", dependencies=[Depends(verify_csrf)])
async def reinject_bulk(request: Request, status: str = Form(...)):
    if status not in FAIL_STATUSES:
        _flash(request, f"잘못된 상태값입니다: {status}", level="danger")
        return RedirectResponse("/urls", status_code=303)

    with get_engine().connect() as conn:
        count = crawl_url_repo.reinject_bulk(conn, status)
    _flash(request, f"{count}개 URL을 재투입했습니다.")
    return RedirectResponse("/urls", status_code=303)
