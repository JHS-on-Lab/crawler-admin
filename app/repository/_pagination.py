"""페이지네이션 공용 헬퍼 — WHERE 절 조립은 같고 SELECT 컬럼/JOIN 만 다른 목록
조회(crawl_url_repo.list_failed_urls, collection_log_repo.list_logs 등)에서
재사용한다."""

from __future__ import annotations

from sqlalchemy import Connection, text


def paginate_query(
    conn: Connection,
    select_sql: str,
    count_sql: str,
    where: list[str],
    params: dict,
    page: int,
    page_size: int,
) -> tuple[list, int]:
    """where 절을 AND 로 묶어 select_sql/count_sql 의 "{where_sql}" 자리에 채우고,
    LIMIT/OFFSET 을 적용해 (행 목록, 전체 건수) 를 반환한다.

    select_sql 은 "... WHERE {where_sql} ... LIMIT :limit OFFSET :offset" 형태여야
    한다. count_sql 실행 시에는 params 에서 limit/offset 을 제외하고 넘긴다 — 두
    값은 COUNT(*) 쿼리의 WHERE 절에 쓰이지 않기 때문이다. "{where_sql}" 치환은
    SQL에 다른 중괄호가 섞여도 안전하도록 str.format() 대신 replace() 를 쓴다."""
    where_sql = " AND ".join(where)
    query_params = {**params, "limit": page_size, "offset": (page - 1) * page_size}

    rows = conn.execute(
        text(select_sql.replace("{where_sql}", where_sql)), query_params
    ).mappings().all()

    count_params = {k: v for k, v in query_params.items() if k not in ("limit", "offset")}
    total = conn.execute(
        text(count_sql.replace("{where_sql}", where_sql)), count_params
    ).scalar()

    return rows, total or 0
