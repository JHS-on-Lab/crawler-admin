"""대시보드 — URL 큐 현황 + 일별 수집 통계."""

from datetime import date

from fastapi import APIRouter, Request

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import crawl_url_repo, collection_log_repo, keyword_repo

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, run_date: str | None = None):
    today = date.today().isoformat()
    run_date = run_date or today

    with get_engine().connect() as conn:
        status_summary = crawl_url_repo.get_status_summary(conn)
        keyword_counts = keyword_repo.get_source_type_counts(conn)
        date_stats = collection_log_repo.get_date_stats(conn, run_date)

    status_map = {row["status"]: row["cnt"] for row in status_summary}

    # discovery / extraction 각각 totals + per-source 분리
    discovery_rows = [r for r in date_stats if r["run_type"] == "discovery"]
    extraction_rows = [r for r in date_stats if r["run_type"] == "extraction"]

    discovery_total = {
        "run_count":      sum(r["run_count"] or 0 for r in discovery_rows),
        "total_found":    sum(r["total_found"] or 0 for r in discovery_rows),
        "total_inserted": sum(r["total_inserted"] or 0 for r in discovery_rows),
        "total_skipped":  sum(r["total_skipped"] or 0 for r in discovery_rows),
    }
    extraction_total = {
        "run_count":       sum(r["run_count"] or 0 for r in extraction_rows),
        "total_attempted": sum(r["total_attempted"] or 0 for r in extraction_rows),
        "total_success":   sum(r["total_success"] or 0 for r in extraction_rows),
        "total_failed":    sum(r["total_failed"] or 0 for r in extraction_rows),
    }

    return templates.TemplateResponse("dashboard.html", {
        "request":          request,
        "active_page":      "dashboard",
        "status_map":       status_map,
        "keyword_counts":   keyword_counts,
        "run_date":         run_date,
        "today":            today,
        "discovery_total":  discovery_total,
        "discovery_rows":   discovery_rows,
        "extraction_total": extraction_total,
        "extraction_rows":  extraction_rows,
    })
