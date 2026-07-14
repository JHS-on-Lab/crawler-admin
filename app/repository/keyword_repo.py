"""t_keyword CRUD."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Connection, text


_SORT_COLS = {
    "id", "keyword", "source_type", "priority", "interval_seconds",
    "next_discover_at", "enabled",
}

# list_keywords 의 stats_from_date 로 LEFT JOIN 됐을 때만 정렬 가능한 계산 컬럼
_STATS_SORT_COLS = {"total_collected"}


def list_keywords(
    conn: Connection,
    source_type: str | None = None,
    enabled: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    stats_from_date: date | None = None,
) -> list:
    """키워드 목록을 조회한다.

    stats_from_date 를 주면 t_crawl_url 을 keyword_id 로 집계한 total_collected
    (해당 날짜 이후 collected_date 건수)를 각 행에 함께 붙인다 — 목록 화면의
    "최근 N일 합계" 정렬 가능 컬럼용. 401~1000개 규모에서도 매 행에 일별 데이터를
    실어보내는 대신 합계 숫자 하나만 계산해 가볍게 유지한다.
    """
    select_cols = "k.*"
    join_clause = ""
    params: dict = {}
    if stats_from_date is not None:
        select_cols = "k.*, COALESCE(stats.total_collected, 0) AS total_collected"
        join_clause = """
            LEFT JOIN (
                SELECT keyword_id, COUNT(*) AS total_collected
                FROM t_crawl_url
                WHERE collected_date >= :stats_from_date
                GROUP BY keyword_id
            ) stats ON stats.keyword_id = k.id
        """
        params["stats_from_date"] = stats_from_date

    q = f"SELECT {select_cols} FROM t_keyword k {join_clause} WHERE 1=1"
    if source_type:
        q += " AND k.source_type = :source_type"
        params["source_type"] = source_type
    if enabled is not None:
        q += " AND k.enabled = :enabled"
        params["enabled"] = 1 if enabled == "true" else 0
    if search:
        q += " AND (k.keyword LIKE :search OR k.display_name LIKE :search)"
        params["search"] = f"%{search}%"

    sortable = _SORT_COLS | (_STATS_SORT_COLS if stats_from_date is not None else set())
    if sort_by and sort_by in sortable:
        direction = "DESC" if sort_order == "desc" else "ASC"
        col = sort_by if sort_by in _STATS_SORT_COLS else f"k.{sort_by}"
        q += f" ORDER BY {col} {direction}"
    else:
        q += " ORDER BY k.source_type, k.priority DESC, k.keyword"
    return conn.execute(text(q), params).mappings().all()


def get_daily_counts(conn: Connection, keyword_id: int, from_date: date) -> list:
    """keyword_id 하나의 collected_date 별 수집 건수(from_date 이후, 0건인 날짜는 빠짐)."""
    return conn.execute(text("""
        SELECT collected_date, COUNT(*) AS cnt
        FROM t_crawl_url
        WHERE keyword_id = :keyword_id AND collected_date >= :from_date
        GROUP BY collected_date
        ORDER BY collected_date
    """), {"keyword_id": keyword_id, "from_date": from_date}).mappings().all()


def get_keyword(conn: Connection, keyword_id: int):
    return conn.execute(
        text("SELECT * FROM t_keyword WHERE id = :id"),
        {"id": keyword_id},
    ).mappings().first()


def create_keyword(
    conn: Connection,
    keyword: str,
    source_type: str,
    display_name: str | None,
    priority: int,
    interval_seconds: int,
) -> None:
    conn.execute(text("""
        INSERT INTO t_keyword (keyword, source_type, display_name, priority, interval_seconds, enabled)
        VALUES (:keyword, :source_type, :display_name, :priority, :interval_seconds, true)
    """), {
        "keyword": keyword,
        "source_type": source_type,
        "display_name": display_name or None,
        "priority": priority,
        "interval_seconds": interval_seconds,
    })
    conn.commit()


def update_keyword(
    conn: Connection,
    keyword_id: int,
    keyword: str,
    display_name: str | None,
    priority: int,
    interval_seconds: int,
) -> None:
    conn.execute(text("""
        UPDATE t_keyword
        SET keyword = :keyword, display_name = :display_name,
            priority = :priority, interval_seconds = :interval_seconds
        WHERE id = :id
    """), {
        "keyword": keyword,
        "display_name": display_name or None,
        "priority": priority,
        "interval_seconds": interval_seconds,
        "id": keyword_id,
    })
    conn.commit()


def toggle_enabled(conn: Connection, keyword_id: int, enabled: bool, disabled_reason: str | None = None) -> None:
    conn.execute(text("""
        UPDATE t_keyword SET enabled = :enabled, disabled_reason = :reason WHERE id = :id
    """), {"enabled": enabled, "reason": None if enabled else disabled_reason, "id": keyword_id})
    conn.commit()


def trigger_now(conn: Connection, keyword_id: int) -> None:
    conn.execute(
        text("UPDATE t_keyword SET next_discover_at = NULL, retry_pending = 0 WHERE id = :id"),
        {"id": keyword_id},
    )
    conn.commit()


def get_source_type_counts(conn: Connection) -> list:
    return conn.execute(text("""
        SELECT source_type,
               COUNT(*) AS total,
               SUM(enabled) AS enabled_cnt
        FROM t_keyword
        GROUP BY source_type
        ORDER BY source_type
    """)).mappings().all()
