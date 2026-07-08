"""t_domain 조회 및 수정."""

from __future__ import annotations

import json

from sqlalchemy import Connection, text


# NOT NULL 컬럼 — 직접 정렬 안전
_SORT_COLS = {"host", "recent_fail_count", "excluded"}

# rules_enabled: rules_json NULL 행도 DEFAULT 1이라 CASE로 3단계 구분
_RULES_SORT_EXPR = (
    "CASE WHEN rules_json IS NULL THEN 0 "
    "WHEN rules_enabled = 0 THEN 1 "
    "ELSE 2 END"
)

# render_mode: NULL은 'static'과 동일하게 표시되므로 COALESCE로 묶어서 정렬
_COALESCE_SORT = {
    "render_mode": "COALESCE(render_mode, 'static')",
}

# NULL이 항상 마지막에 와야 하는 컬럼 (NULL = 데이터 없음 / 기본값)
#   crawl_delay_ms: NULL = "기본값" — 0ms보다 앞에 정렬되면 혼란
#   success_rate:   NULL = 수집 이력 없음 — 0%보다 앞에 정렬되면 혼란
#   cooldown_until: NULL = 쿨다운 없음 — 쿨다운 중인 행이 앞에 와야 자연스러움
_NULL_LAST_COLS = {"crawl_delay_ms", "success_rate", "cooldown_until"}


def list_domains(
    conn: Connection,
    search: str | None = None,
    rules_filter: str | None = None,
    excluded_filter: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> list:
    q = "SELECT * FROM t_domain WHERE 1=1"
    params: dict = {}
    if search:
        q += " AND host LIKE :search"
        params["search"] = f"%{search}%"
    if rules_filter == "active":
        q += " AND rules_json IS NOT NULL AND rules_enabled = 1"
    elif rules_filter == "inactive":
        q += " AND rules_json IS NOT NULL AND rules_enabled = 0"
    elif rules_filter == "none":
        q += " AND rules_json IS NULL"
    if excluded_filter == "blocked":
        q += " AND excluded = 1"
    elif excluded_filter == "not_blocked":
        q += " AND excluded = 0"
    direction = "DESC" if sort_order == "desc" else "ASC"
    if sort_by == "rules_enabled":
        q += f" ORDER BY {_RULES_SORT_EXPR} {direction}"
    elif sort_by in _COALESCE_SORT:
        q += f" ORDER BY {_COALESCE_SORT[sort_by]} {direction}"
    elif sort_by in _NULL_LAST_COLS:
        q += f" ORDER BY ISNULL({sort_by}), {sort_by} {direction}"
    elif sort_by and sort_by in _SORT_COLS:
        q += f" ORDER BY {sort_by} {direction}"
    else:
        q += " ORDER BY recent_fail_count DESC, host"
    return conn.execute(text(q), params).mappings().all()


def get_domain(conn: Connection, host: str):
    return conn.execute(
        text("SELECT * FROM t_domain WHERE host = :host"),
        {"host": host},
    ).mappings().first()


def update_rules(conn: Connection, host: str, rules_json: str, rules_enabled: bool) -> None:
    parsed = json.loads(rules_json)  # 저장 전 JSON 유효성 검증
    conn.execute(text("""
        UPDATE t_domain
        SET rules_json = :rules_json, rules_enabled = :rules_enabled,
            rules_version = rules_version + 1, updated_by = 'admin'
        WHERE host = :host
    """), {
        "rules_json": json.dumps(parsed, ensure_ascii=False),
        "rules_enabled": rules_enabled,
        "host": host,
    })
    conn.commit()


def toggle_rules_enabled(conn: Connection, host: str, enabled: bool) -> None:
    conn.execute(text("""
        UPDATE t_domain SET rules_enabled = :enabled, updated_by = 'admin' WHERE host = :host
    """), {"enabled": enabled, "host": host})
    conn.commit()


def toggle_excluded(conn: Connection, host: str, excluded: bool) -> None:
    conn.execute(text("""
        UPDATE t_domain SET excluded = :excluded, updated_by = 'admin' WHERE host = :host
    """), {"excluded": excluded, "host": host})
    conn.commit()


def block_domain(conn: Connection, host: str) -> None:
    """아직 t_domain에 행이 없는 도메인도 선제 차단할 수 있도록 upsert한다."""
    conn.execute(text("""
        INSERT INTO t_domain (host, excluded, updated_by)
        VALUES (:host, 1, 'admin')
        ON DUPLICATE KEY UPDATE excluded = 1, updated_by = 'admin'
    """), {"host": host})
    conn.commit()


def clear_cooldown(conn: Connection, host: str) -> None:
    conn.execute(text("""
        UPDATE t_domain
        SET cooldown_until = NULL, recent_fail_count = 0, updated_by = 'admin'
        WHERE host = :host
    """), {"host": host})
    conn.commit()
