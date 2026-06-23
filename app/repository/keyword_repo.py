"""t_keyword CRUD."""

from __future__ import annotations

from sqlalchemy import Connection, text


def list_keywords(conn: Connection, source_type: str | None = None, enabled: str | None = None) -> list:
    q = "SELECT * FROM t_keyword WHERE 1=1"
    params: dict = {}
    if source_type:
        q += " AND source_type = :source_type"
        params["source_type"] = source_type
    if enabled is not None:
        q += " AND enabled = :enabled"
        params["enabled"] = 1 if enabled == "true" else 0
    q += " ORDER BY source_type, priority DESC, keyword"
    return conn.execute(text(q), params).mappings().all()


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
