"""대시보드 — URL 큐 현황 + 최근 수집 이력."""

from fastapi import APIRouter, Request

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import crawl_url_repo, collection_log_repo, keyword_repo

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    with get_engine().connect() as conn:
        status_summary = crawl_url_repo.get_status_summary(conn)
        source_summary = crawl_url_repo.get_status_summary_by_source(conn)
        keyword_counts = keyword_repo.get_source_type_counts(conn)
        recent_logs, _ = collection_log_repo.list_logs(conn, page=1)

    status_map = {row["status"]: row["cnt"] for row in status_summary}

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "status_map": status_map,
        "source_summary": source_summary,
        "keyword_counts": keyword_counts,
        "recent_logs": recent_logs[:10],
    })
