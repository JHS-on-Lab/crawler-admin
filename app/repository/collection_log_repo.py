"""t_collection_log 조회."""

from __future__ import annotations

from sqlalchemy import Connection, text

PAGE_SIZE = 50


def list_logs(
    conn: Connection,
    run_type: str | None = None,
    source_type: str | None = None,
    from_date: str | None = None,
    page: int = 1,
) -> tuple[list, int]:
    where = ["1=1"]
    params: dict = {}

    if run_type:
        where.append("cl.run_type = :run_type")
        params["run_type"] = run_type
    if source_type:
        where.append("cl.source_type = :source_type")
        params["source_type"] = source_type
    if from_date:
        where.append("cl.run_date >= :from_date")
        params["from_date"] = from_date

    where_sql = " AND ".join(where)
    offset = (page - 1) * PAGE_SIZE
    params.update({"limit": PAGE_SIZE, "offset": offset})

    rows = conn.execute(text(f"""
        SELECT cl.*, k.keyword, k.display_name
        FROM t_collection_log cl
        LEFT JOIN t_keyword k ON cl.keyword_id = k.id
        WHERE {where_sql}
        ORDER BY cl.started_at DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    total = conn.execute(text(f"""
        SELECT COUNT(*) FROM t_collection_log cl WHERE {where_sql}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return rows, total or 0


def get_date_stats(conn: Connection, run_date: str) -> list:
    """특정 일자의 run_type × source_type 집계를 반환한다."""
    return conn.execute(text("""
        SELECT run_type, source_type,
               COUNT(*) AS run_count,
               SUM(urls_found)    AS total_found,
               SUM(urls_inserted) AS total_inserted,
               SUM(urls_skipped)  AS total_skipped,
               SUM(urls_attempted) AS total_attempted,
               SUM(urls_success)  AS total_success,
               SUM(urls_failed)   AS total_failed
        FROM t_collection_log
        WHERE run_date = :run_date
        GROUP BY run_type, source_type
        ORDER BY run_type, source_type
    """), {"run_date": run_date}).mappings().all()


def get_daily_summary(conn: Connection, days: int = 7) -> list:
    return conn.execute(text("""
        SELECT run_date, run_type, source_type,
               COUNT(*) AS run_count,
               SUM(urls_found) AS total_found,
               SUM(urls_inserted) AS total_inserted,
               SUM(urls_success) AS total_success,
               SUM(urls_failed) AS total_failed
        FROM t_collection_log
        WHERE run_date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        GROUP BY run_date, run_type, source_type
        ORDER BY run_date DESC, run_type, source_type
    """), {"days": days}).mappings().all()
