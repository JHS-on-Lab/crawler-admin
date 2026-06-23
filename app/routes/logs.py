"""수집 이력 조회."""

from fastapi import APIRouter, Request

from app.tmpl import templates
from app.repository.db import get_engine
from app.repository import collection_log_repo

router = APIRouter(prefix="/logs")

SOURCE_TYPES = ["NAVER_NEWS", "DAUM_NEWS", "GOOGLE_NEWS", "BAIDU_NEWS", "NAVER_STOCK"]


@router.get("")
async def list_logs(
    request: Request,
    run_type: str = "",
    source_type: str = "",
    from_date: str = "",
    page: int = 1,
):
    with get_engine().connect() as conn:
        rows, total = collection_log_repo.list_logs(
            conn,
            run_type=run_type or None,
            source_type=source_type or None,
            from_date=from_date or None,
            page=page,
        )

    total_pages = (total + collection_log_repo.PAGE_SIZE - 1) // collection_log_repo.PAGE_SIZE

    return templates.TemplateResponse("logs/list.html", {
        "request": request,
        "active_page": "logs",
        "rows": rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "source_types": SOURCE_TYPES,
        "filter_run_type": run_type,
        "filter_source": source_type,
        "filter_from_date": from_date,
    })
