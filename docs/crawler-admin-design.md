# crawler-admin — 설계 문서

> discovery-worker · extraction-worker · rescrape-dispatcher 운영을 위한 내부 웹 관리 도구.
> 명세에서 벗어나야 할 경우 이 문서를 먼저 갱신한다.

---

## 1. 개요

discovery-worker 및 extraction-worker 가 사용하는 MySQL DB(`crawlerdb`)에 직접 접속해
키워드 등록·수집 오류 모니터링·도메인 규칙 관리·수집 이력 조회를 웹 UI로 제공하는
**내부 운영 전용** 관리 도구다.

- **대상 DB**: discovery-worker / extraction-worker 와 동일한 RDS (`crawlerdb` 스키마)
- **접근 방식**: 별도 API 없이 DB 직접 읽기/쓰기
- **인증**: 단일 관리자 계정 (환경변수 설정)
- **배포**: Docker 컨테이너 단일 인스턴스

### 1.1 네 프로젝트의 관계

```
discovery-worker    extraction-worker    rescrape-dispatcher    crawler-admin
────────────────    ─────────────────    ───────────────────    ─────────────────────
URL 발견             본문 추출             Solr → t_crawl_url     t_keyword CRUD
  → t_crawl_url       → t_crawl_url                               t_crawl_url 모니터링
                       → Solr                                     t_domain 규칙 편집
                                                                  t_collection_log 조회
         ╲                  ╲                  ╱                      │
          └──────────── MySQL (crawlerdb) ──────────────────────────┘
```

crawler-admin 은 **읽기 전용이 아니다.** 키워드 등록·수정·비활성화, URL 재투입, 도메인 규칙 편집 등 운영에 필요한 쓰기 작업을 수행한다.

---

## 2. 아키텍처

```
브라우저
  │  HTTP (Bootstrap 5 UI)
  ▼
FastAPI (uvicorn)
  │  SessionMiddleware (signed cookie)
  │  RequireLoginMiddleware
  │
  ├── GET/POST /login, GET /logout
  ├── GET /               → dashboard.py
  ├── GET/POST /keywords  → keywords.py
  ├── GET/POST /urls      → urls.py
  ├── GET/POST /domains   → domains.py
  └── GET /logs           → logs.py
          │
          ▼  SQLAlchemy Core
    MySQL (RDS)  ←  SSH Tunnel (로컬/NAT 환경)
    crawlerdb
      ├── t_keyword
      ├── t_crawl_url
      ├── t_domain
      └── t_collection_log
```

### 2.1 서버사이드 렌더링

Jinja2 템플릿으로 HTML을 서버에서 생성한다. JavaScript 빌드 단계 없음.
Bootstrap 5 + Bootstrap Icons 는 CDN으로 로드한다.

### 2.2 인증 흐름

1. 미인증 요청 → `RequireLoginMiddleware` 가 `/login` 으로 리다이렉트
2. `POST /login` → `ADMIN_USER` / `ADMIN_PASSWORD` 를 `secrets.compare_digest` 로 상수시간 비교
3. 성공 시 세션 쿠키(`itsdangerous` 서명) 발급, 24시간 유효, 실패 카운터 초기화
4. `/logout` → 세션 삭제

공개 경로: `/login`, `/favicon.ico` 만 인증 없이 접근 가능.

**로그인 시도 제한** (`app/routes/auth.py`): 클라이언트 IP 별로 실패 횟수를 인메모리로
추적한다. 15분 내 5회 실패하면 그 이후 요청은 자격증명 확인 없이 즉시 429로 거절된다
(brute force 방어). 워커 프로세스 재시작 시 카운터는 초기화된다.

### 2.3 CSRF 보호

`app/csrf.py` — synchronizer token 패턴. 세션마다 랜덤 토큰을 한 번 발급해 `Jinja2Templates`
의 `context_processors` 로 모든 템플릿 렌더링에 `csrf_token` 을 자동 주입하고, 각 폼은
`<input type="hidden" name="csrf_token">` 로 이를 실어 보낸다. state-changing POST 라우트
(로그인 포함 총 12개 폼 대응)는 전부 `Depends(verify_csrf)` 로 세션 토큰과 제출된 토큰이
일치하는지 검증하며, 불일치/누락 시 403. `RequireLoginMiddleware` 가 세션 쿠키만으로
인증을 판단하는 구조라 CSRF 방어가 없으면 관리자가 로그인해둔 상태에서 악성 페이지가
대신 상태 변경 요청을 보낼 수 있었다.

---

## 3. 페이지별 기능

### 3.1 대시보드 (`/`)

- **t_crawl_url 상태 요약**: `discovered` / `extracting` / `stored` / `failed_*` / `dead` 건수
- **키워드 현황**: `source_type` 별 전체 / 활성 키워드 수
- **일자별 수집/추출 요약**: 날짜 선택(기본 오늘)에 대한 `t_collection_log` 기반 discovery/extraction 요약
- **추출 실패율 추이**: 최근 7일(`FAILURE_TREND_DAYS`) 추출 실패율 SVG 라인 차트(hover/키보드 인터랙션)

> `crawl_url_repo.get_status_summary_by_source()`(`source_type`×`status` 교차 집계)와
> `collection_log_repo.get_daily_summary()`는 리포지토리에 구현돼 있지만 현재 어떤 라우트에서도
> 호출되지 않는 미사용 코드다 — 향후 대시보드 확장 시 재사용하거나 정리 대상.

### 3.2 키워드 관리 (`/keywords`)

| 기능 | 경로 | 설명 |
|---|---|---|
| 목록 조회 | `GET /keywords` | `source_type` / `enabled` 필터 |
| 신규 등록 | `GET/POST /keywords/new` | keyword, source_type, display_name, priority, interval_seconds |
| 수정 | `GET/POST /keywords/{id}/edit` | keyword, display_name, priority, interval_seconds (source_type 변경 불가) |
| 활성/비활성 | `POST /keywords/{id}/toggle` | 비활성화 시 `disabled_reason` 기록 |
| 즉시 수집 | `POST /keywords/{id}/trigger` | `next_discover_at = NULL` 로 업데이트 → 다음 루프에서 즉시 처리 |
| 일자별 수집 추이 | `GET /keywords/{id}/stats?days=7\|14\|30` | 키워드 1개의 `collected_date` 별 URL 수집 건수 |
| Excel 내보내기 | `GET /keywords/export.xlsx` | 현재 필터/정렬 기준 목록을 xlsx로 다운로드 |

**source_type 값**: `NAVER_NEWS`, `DAUM_NEWS`, `GOOGLE_NEWS`, `BAIDU_NEWS`, `NAVER_STOCK`, `DUCKDUCKGO_NEWS`(운영상 비활성 — 드롭다운/스키마에는 남아있으나 실제 대상 키워드 없음)
(`/keywords`, `/logs` 기준. `/urls` 페이지는 여기에 `SOLR_RESCRAPE`가 추가된 7개 값을 필터로 제공한다 — rescrape-dispatcher가 Solr를 거쳐 `t_crawl_url`에 넣은 URL을 구분하기 위함.)

**최근 N일 합계 컬럼**: 목록 화면에 `t_crawl_url` 을 `keyword_id` 로 집계한 `total_collected`
(기본 최근 7일, 14/30일 전환 가능)를 정렬 가능한 컬럼으로 붙인다. 운영 DB 기준 키워드가
~1000개까지 있어 행마다 일별 스파크라인을 그리면 DOM이 무거워지고 눈으로 훑기도 어려워서,
**목록에는 합계 숫자만**(정렬로 상위/하위를 바로 찾음) 두고 **일자별 상세는 숫자 클릭 시
`/keywords/{id}/stats`로 이동**하는 구조로 분리했다 — 렌더링 비용이 항상 "지금 보는 키워드
1개" 기준이라 전체 키워드 수와 무관하게 가볍다.

### 3.3 실패 URL 재투입 (`/urls`)

실패 상태(`failed_transient`, `failed_permanent`, `dead`) URL 을 조회하고 재투입한다.

| 기능 | 경로 | 설명 |
|---|---|---|
| 전체 상태 요약 | `GET /urls` 상단 | 전체 status 건수 카드 (discovered / extracting / stored 는 정보 표시만) |
| 실패 URL 목록 | `GET /urls` 하단 | `failed_transient` / `failed_permanent` / `dead` 필터, source_type / host 추가 필터, 50건/페이지 |
| 단건 재투입 | `POST /urls/{id}/reinject` | `status=discovered`, `attempt_count=0`, error 컬럼 초기화 |
| 일괄 재투입 | `POST /urls/reinject-bulk` | 특정 실패 status 전체 재투입 |

**재투입 동작**: `status`, `attempt_count`, `last_error_code`, `last_error_msg`, `next_retry_at` 초기화. extraction-worker 가 다음 루프에서 자동 처리.

**서버측 검증**: 두 엔드포인트 모두 대상 URL이 실패 상태(`FAIL_STATUSES` = `failed_transient`/`failed_permanent`/`dead`)일 때만 실제로 갱신한다. 단건 재투입은 `WHERE id=:id AND status IN :fail_statuses` 조건으로, 일괄 재투입은 `status` 파라미터 자체를 사전 검증해서, 조작된 요청으로 이미 완료(`stored`)되거나 처리 중(`extracting`)인 URL이 초기화되는 것을 막는다. 대상이 아니면 실패 flash 메시지를 표시한다.

> 상단 카드 중 `failed_transient` / `failed_permanent` / `dead` 만 클릭 시 해당 status 필터가 적용된다. `discovered` / `extracting` / `stored` 카드는 현황 표시 전용이며 클릭해도 목록이 변하지 않는다.

### 3.4 도메인 규칙 관리 (`/domains`)

| 기능 | 경로 | 설명 |
|---|---|---|
| 목록 조회 | `GET /domains` | host 검색, `recent_fail_count` 내림차순 |
| 규칙 활성/비활성 | `POST /domains/{host}/toggle-rules` | `rules_enabled` 토글 |
| 제외(차단) 토글 | `POST /domains/{host}/toggle-excluded` | `excluded` 토글 — 크롤링 완전 차단 |
| 쿨다운 해제 | `POST /domains/{host}/clear-cooldown` | `cooldown_until = NULL`, `recent_fail_count = 0` |
| 규칙 편집 | `POST /domains/{host}/edit-rules` | `rules_json` JSON 편집 + `rules_version` 자동 증가 |
| 신규 도메인 선제 차단 | `POST /domains/block` | 아직 크롤링 이력이 없는 host도 `t_domain`에 `excluded=1`로 upsert |
| 규칙 요청 폼 생성 | `GET /domains/rule-request-form` | 실패 상위 도메인의 에러메시지·예시 URL을 정리해 복사 가능한 텍스트로 생성 |
| Excel 내보내기 | `GET /domains/export.xlsx` | 현재 필터/정렬 기준 목록을 xlsx로 다운로드 |

규칙 편집 시 저장 전 JSON 유효성 검증. 실패 시 플래시 메시지.
저장된 규칙은 extraction-worker 가 TTL 캐시(기본 60초)로 자동 반영.

**규칙 요청 폼**: `rules_filter=none`(규칙 없는 도메인) + `excluded_filter=not_blocked`
기본값으로 실패 상위 N개(기본 15, 최대 100) 도메인을 뽑아, 도메인별 실패 URL을
`last_error_msg` 로 그룹핑(건수 내림차순)해 그룹당 예시 URL 최대 3개와 함께 텍스트로
조립한다. extraction-worker 의 도메인 규칙을 새로 작성할 때 매번 수동으로 실패
현황을 정리하던 작업을 대체하기 위한 것 — extraction-worker 쪽 워크플로는
`extraction-worker/docs/domain-rule-guide.md` 참고.

`host` 는 다섯 라우트(`toggle-rules`/`toggle-excluded`/`clear-cooldown`/`edit-rules`/`block`) 모두
`.strip().lower()` 로 정규화한 뒤 조회한다(크롤러가 저장한 host와 대소문자가 달라
매칭에 실패하는 것을 방지). 대상 host가 `t_domain` 에 없으면(정규화해도 못 찾으면)
성공 메시지 대신 "찾을 수 없습니다" flash를 표시한다 — 이전에는 조용히 아무 일도
안 일어나 실패 여부를 알 수 없었다.

### 3.5 수집 이력 (`/logs`)

`t_collection_log` 조회. `run_type` / `source_type` / `from_date` 필터.

| 컬럼 | 설명 |
|---|---|
| `run_type` | `discovery` — URL 발견 런, `extraction` — 본문 추출 런 |
| `urls_found` / `urls_inserted` / `urls_skipped` | discovery 전용 |
| `urls_attempted` / `urls_success` / `urls_failed` | extraction 전용 |
| `error_msg` | 런이 예외로 중단됐을 때 이유. NULL = 정상 완료 |

---

## 4. 모듈 구조

```
app/
  __main__.py          # 진입점 — argparse --port, config.validate(), uvicorn.run()
  main.py              # FastAPI 팩토리 — lifespan, 미들웨어 등록, 라우터 마운트
  config.py            # 환경변수 로딩 + validate()
  logging_setup.py     # 로그 파일 핸들러 설정
  middleware.py        # RequireLoginMiddleware
  tmpl.py              # Jinja2Templates 인스턴스 (순환 import 방지용 분리) + csrf_token 자동 주입
  csrf.py              # CSRF synchronizer token 발급/검증 (verify_csrf)
  flash.py             # 세션 플래시 메시지 헬퍼 (routes 3곳 중복 통합)
  excel.py             # xlsx export 공통 모듈 — 수식 인젝션 방어 포함

  repository/
    db.py              # startup()/shutdown() + SSH 터널 + get_engine()
    keyword_repo.py    # t_keyword CRUD
    crawl_url_repo.py  # t_crawl_url 조회 + 재투입
    domain_repo.py     # t_domain 조회 + 규칙 편집
    collection_log_repo.py  # t_collection_log 조회

  routes/
    auth.py            # GET/POST /login, GET /logout
    dashboard.py       # GET /
    keywords.py        # GET/POST /keywords/*
    urls.py            # GET/POST /urls/*
    domains.py         # GET/POST /domains/*
    logs.py            # GET /logs

  templates/
    base.html          # 다크 사이드바 레이아웃 (Bootstrap 5)
    login.html         # 인증 화면
    dashboard.html
    keywords/list.html, form.html, stats.html
    urls/list.html
    domains/list.html, rule_request_form.html
    logs/list.html
```

### 4.1 미들웨어 순서

```python
app.add_middleware(RequireLoginMiddleware)   # 내부 (나중에 실행)
app.add_middleware(SessionMiddleware, ...)   # 외부 (먼저 실행)
```

Starlette 미들웨어는 추가 역순으로 실행된다.
`SessionMiddleware` 가 먼저 세션을 복원해야 `RequireLoginMiddleware` 가 `session["authenticated"]` 를 읽을 수 있다.

---

## 5. 기술 스택

| 역할 | 라이브러리 |
|---|---|
| 웹 프레임워크 | FastAPI 0.115 + uvicorn |
| 템플릿 | Jinja2 3.1 + python-multipart(폼 파싱) |
| 세션 | `starlette.middleware.sessions.SessionMiddleware` (itsdangerous 서명 쿠키) |
| DB 접근 | SQLAlchemy 2.0 Core (ORM 미사용) + PyMySQL |
| SSH 터널 | sshtunnel + paramiko |
| 설정 | python-dotenv |
| UI | Bootstrap 5 + Bootstrap Icons (CDN) |

---

## 6. 설정 키 전체 목록

| 키 | 기본값 | 설명 |
|---|---|---|
| `RDS_HOST` | (필수) | MySQL 호스트 |
| `RDS_PORT` | `3306` | MySQL 포트 |
| `RDS_USER` | (필수) | MySQL 사용자 |
| `RDS_PASSWORD` | (필수) | MySQL 비밀번호 |
| `RDS_CRAWLER_DB` | (필수, 코드 기본값은 빈 문자열) | 접속 스키마 (배포용 `.env`는 `crawlerdb`) |
| `TUNNEL_ENABLED` | `false` | SSH 터널 사용 여부 |
| `TUNNEL_SSH_HOST` | — | SSH 서버 호스트 |
| `TUNNEL_SSH_PORT` | `22` | SSH 서버 포트 |
| `TUNNEL_SSH_USER` | `ubuntu` | SSH 사용자 |
| `TUNNEL_SSH_KEY_PATH` | — | SSH 키 파일 경로 |
| `TUNNEL_LOCAL_PORT` | `13306` | 로컬 터널 포트 |
| `PORT` | `8000` | 웹 서버 포트 |
| `ADMIN_USER` | `admin` | 관리자 로그인 아이디 |
| `ADMIN_PASSWORD` | (필수) | 관리자 비밀번호 |
| `SESSION_SECRET` | 코드 기본값 `change-me` (배포용 `.env`는 `change-me-in-production`) | 세션 쿠키 서명 키. 두 플레이스홀더 값 모두 검증 실패를 유발하므로 운영 환경에서 반드시 교체 |
| `LOG_DIR` | `./logs` | 로그 디렉토리 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `LOG_ROTATION` | `daily` | 로그 로테이션 방식 (`daily` \| `size`) |
| `LOG_RETAIN_DAYS` | `30` | daily 모드: 보관 일수 |
| `LOG_BACKUP_COUNT` | `10` | size 모드: 보관 파일 수 |

---

## 7. 로그 파일

| 파일 | 내용 |
|---|---|
| `{LOG_DIR}/admin.log` | 정상 동작·요청 (INFO 이상) |
| `{LOG_DIR}/admin-error.log` | WARNING 이상만 |

---

## 8. 범위 밖

- 다중 관리자 계정 — 내부 단독 사용 용도이므로 단일 계정으로 충분
- 실시간 로그 스트리밍 — 별도 로그 뷰어 또는 `docker logs -f` 사용
- 수집 워커 직접 기동/중단 — Docker/서버 레벨에서 처리
- 추출 규칙 미리보기(URL 테스트) — extraction-worker 의 `scripts/run_extraction.py` 사용
