"""t_domain 조회 및 수정."""

from __future__ import annotations

import json

from sqlalchemy import Connection, text


def list_domains(conn: Connection, search: str | None = None) -> list:
    q = "SELECT * FROM t_domain WHERE 1=1"
    params: dict = {}
    if search:
        q += " AND host LIKE :search"
        params["search"] = f"%{search}%"
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


def clear_cooldown(conn: Connection, host: str) -> None:
    conn.execute(text("""
        UPDATE t_domain
        SET cooldown_until = NULL, recent_fail_count = 0, updated_by = 'admin'
        WHERE host = :host
    """), {"host": host})
    conn.commit()
