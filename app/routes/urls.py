"""URL 큐 조회 및 재투입."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import crawl_url_repo

router = APIRouter(prefix="/urls")

SOURCE_TYPES = ["NAVER_NEWS", "DAUM_NEWS", "GOOGLE_NEWS", "BAIDU_NEWS", "NAVER_STOCK", "DUCKDUCKGO_NEWS", "SOLR_RESCRAPE"]
FAIL_STATUSES = ["failed_transient", "failed_permanent", "dead"]


def _flash(request: Request, msg: str, level: str = "success") -> None:
    request.session["flash"] = {"msg": msg, "level": level}


@router.get("")
async def list_urls(
    request: Request,
    status: str = "",
    source_type: str = "",
    host: str = "",
    page: int = 1,
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


@router.post("/{url_id}/reinject")
async def reinject(request: Request, url_id: int):
    with get_engine().connect() as conn:
        crawl_url_repo.reinject(conn, url_id)
    _flash(request, "URL을 재투입했습니다.")
    return RedirectResponse("/urls", status_code=303)


@router.post("/reinject-bulk")
async def reinject_bulk(request: Request, status: str = Form(...)):
    with get_engine().connect() as conn:
        count = crawl_url_repo.reinject_bulk(conn, status)
    _flash(request, f"{count}개 URL을 재투입했습니다.")
    return RedirectResponse("/urls", status_code=303)
