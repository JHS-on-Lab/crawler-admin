"""여러 라우트가 공유하는 상수. discovery-worker 의 SourceType 과 값이 맞아야 한다."""

from __future__ import annotations

SOURCE_TYPES = [
    "NAVER_NEWS", "DAUM_NEWS", "GOOGLE_NEWS", "BAIDU_NEWS",
    "NAVER_STOCK", "DUCKDUCKGO_NEWS", "BAOMOI_NEWS", "TINHTE_FORUM",
]

# t_crawl_url 전용 — rescrape-dispatcher 가 Solr 재수집으로 넣는 URL 은 대응하는
# t_keyword 가 없어(키워드 기반 발견이 아니라 Solr 조회로 채워짐) SOURCE_TYPES 에
# 없는 SOLR_RESCRAPE 값을 갖는다.
URL_SOURCE_TYPES = SOURCE_TYPES + ["SOLR_RESCRAPE"]
