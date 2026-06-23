"""t_crawl_url 조회 및 상태 변경."""

from __future__ import annotations

from sqlalchemy import Connection, text

PAGE_SIZE = 50


def get_status_summary(conn: Connection) -> list:
    return conn.execute(text("""
        SELECT status, COUNT(*) AS cnt
        FROM t_crawl_url
        GROUP BY status
        ORDER BY FIELD(status,
            'discovered','extracting','stored',
            'failed_transient','failed_permanent','dead')
    """)).mappings().all()


def get_status_summary_by_source(conn: Connection) -> list:
    return conn.execute(text("""
        SELECT source_type, status, COUNT(*) AS cnt
        FROM t_crawl_url
        GROUP BY source_type, status
        ORDER BY source_type, status
    """)).mappings().all()


def list_failed_urls(
    conn: Connection,
    status: str | None = None,
    source_type: str | None = None,
    host: str | None = None,
    page: int = 1,
) -> tuple[list, int]:
    _FAIL_STATUSES = ("failed_transient", "failed_permanent", "dead")
    where = [f"cu.status IN ('failed_transient','failed_permanent','dead')"]
    params: dict = {}

    if status:
        if status not in _FAIL_STATUSES:
            return [], 0
        where = ["cu.status = :status"]
        params["status"] = status
    if source_type:
        where.append("cu.source_type = :source_type")
        params["source_type"] = source_type
    if host:
        where.append("cu.host LIKE :host")
        params["host"] = f"%{host}%"

    where_sql = " AND ".join(where)
    offset = (page - 1) * PAGE_SIZE
    params.update({"limit": PAGE_SIZE, "offset": offset})

    rows = conn.execute(text(f"""
        SELECT cu.id, cu.url, cu.host, cu.source_type, cu.status,
               cu.attempt_count, cu.last_error_code, cu.last_error_msg,
               cu.updated_at, cu.priority,
               k.keyword, k.display_name
        FROM t_crawl_url cu
        LEFT JOIN t_keyword k ON cu.keyword_id = k.id
        WHERE {where_sql}
        ORDER BY cu.updated_at DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    total = conn.execute(text(f"""
        SELECT COUNT(*) AS cnt FROM t_crawl_url cu WHERE {where_sql}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return rows, total or 0


def reinject(conn: Connection, url_id: int) -> None:
    conn.execute(text("""
        UPDATE t_crawl_url
        SET status = 'discovered', attempt_count = 0,
            last_error_code = NULL, last_error_msg = NULL, next_retry_at = NULL
        WHERE id = :id
    """), {"id": url_id})
    conn.commit()


def reinject_bulk(conn: Connection, status: str) -> int:
    result = conn.execute(text("""
        UPDATE t_crawl_url
        SET status = 'discovered', attempt_count = 0,
            last_error_code = NULL, last_error_msg = NULL, next_retry_at = NULL
        WHERE status = :status
    """), {"status": status})
    conn.commit()
    return result.rowcount
