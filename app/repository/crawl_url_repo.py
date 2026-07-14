"""t_crawl_url 조회 및 상태 변경."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import Connection, bindparam, text

PAGE_SIZE = 50

# 재투입(reinject) 가능한 상태. list_failed_urls 필터 검증, reinject_bulk 검증,
# routes/urls.py 의 select 옵션 렌더링까지 이 하나의 정의를 공유한다 — 예전엔
# urls.py 에 별도로 같은 목록이 복붙돼 있어서 서로 어긋날 위험이 있었다.
FAIL_STATUSES = ("failed_transient", "failed_permanent", "dead")


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
    where = [f"cu.status IN ('failed_transient','failed_permanent','dead')"]
    params: dict = {}

    if status:
        if status not in FAIL_STATUSES:
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


def get_failure_groups(
    conn: Connection, host: str, max_urls_per_group: int = 3, scan_limit: int = 500,
) -> list[dict]:
    """host의 실패 URL을 last_error_msg 로 그룹핑해 건수 내림차순으로 반환.

    그룹당 예시 URL은 최근 것부터 max_urls_per_group개까지만 담는다. 실패 건수가
    많은 도메인이라도 최근 scan_limit건만 훑어 집계 부담을 제한한다(도메인 규칙
    작성 참고용이라 정확한 전체 카운트보다 최근 경향 파악이 목적).
    """
    rows = conn.execute(text("""
        SELECT url, last_error_msg
        FROM t_crawl_url
        WHERE host = :host AND status IN ('failed_transient','failed_permanent','dead')
        ORDER BY updated_at DESC
        LIMIT :scan_limit
    """), {"host": host, "scan_limit": scan_limit}).mappings().all()

    counts: Counter = Counter(row["last_error_msg"] for row in rows)
    urls_by_msg: dict[str | None, list[str]] = defaultdict(list)
    for row in rows:
        msg = row["last_error_msg"]
        if len(urls_by_msg[msg]) < max_urls_per_group:
            urls_by_msg[msg].append(row["url"])

    return [
        {"error_msg": msg, "count": cnt, "urls": urls_by_msg[msg]}
        for msg, cnt in counts.most_common()
    ]


def reinject(conn: Connection, url_id: int) -> bool:
    """실패 상태(FAIL_STATUSES)인 URL 하나를 discovered 로 되돌린다.

    WHERE 절에 상태 조건을 명시해, 이미 stored/extracting 인 URL이 조작된
    요청(잘못된 id 등)으로 실수로 초기화되는 것을 막는다.
    반환: 실제로 갱신됐으면 True, 대상이 없거나(잘못된 id) 이미 실패 상태가
    아니었으면 False.
    """
    result = conn.execute(text("""
        UPDATE t_crawl_url
        SET status = 'discovered', attempt_count = 0,
            last_error_code = NULL, last_error_msg = NULL, next_retry_at = NULL
        WHERE id = :id AND status IN :fail_statuses
    """).bindparams(bindparam("fail_statuses", expanding=True)),
        {"id": url_id, "fail_statuses": list(FAIL_STATUSES)})
    conn.commit()
    return result.rowcount > 0


def reinject_bulk(conn: Connection, status: str) -> int:
    """status 상태인 URL 을 전부 discovered 로 되돌린다.

    status 가 FAIL_STATUSES 에 없으면 아무것도 하지 않고 0을 반환한다 —
    조작된 요청으로 stored/extracting 같은 상태를 통째로 초기화하는 것을 막는다.
    """
    if status not in FAIL_STATUSES:
        return 0

    result = conn.execute(text("""
        UPDATE t_crawl_url
        SET status = 'discovered', attempt_count = 0,
            last_error_code = NULL, last_error_msg = NULL, next_retry_at = NULL
        WHERE status = :status
    """), {"status": status})
    conn.commit()
    return result.rowcount
