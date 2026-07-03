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
  ├── GET/POST /login, /logout
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
2. `POST /login` → `ADMIN_USER` / `ADMIN_PASSWORD` 검증
3. 성공 시 세션 쿠키(`itsdangerous` 서명) 발급, 24시간 유효
4. `/logout` → 세션 삭제

공개 경로: `/login`, `/favicon.ico` 만 인증 없이 접근 가능.

---

## 3. 페이지별 기능

### 3.1 대시보드 (`/`)

- **t_crawl_url 상태 요약**: `discovered` / `extracting` / `stored` / `failed_*` / `dead` 건수
- **소스별 현황**: `source_type` × `status` 교차 집계
- **키워드 현황**: `source_type` 별 전체 / 활성 키워드 수
- **최근 수집 이력**: `t_collection_log` 최근 10건

### 3.2 키워드 관리 (`/keywords`)

| 기능 | 경로 | 설명 |
|---|---|---|
| 목록 조회 | `GET /keywords` | `source_type` / `enabled` 필터 |
| 신규 등록 | `GET/POST /keywords/new` | keyword, source_type, display_name, priority, interval_seconds |
| 수정 | `GET/POST /keywords/{id}/edit` | keyword, display_name, priority, interval_seconds (source_type 변경 불가) |
| 활성/비활성 | `POST /keywords/{id}/toggle` | 비활성화 시 `disabled_reason` 기록 |
| 즉시 수집 | `POST /keywords/{id}/trigger` | `next_discover_at = NULL` 로 업데이트 → 다음 루프에서 즉시 처리 |

**source_type 값**: `NAVER_NEWS`, `DAUM_NEWS`, `GOOGLE_NEWS`, `BAIDU_NEWS`, `NAVER_STOCK`, `DUCKDUCKGO_NEWS`

### 3.3 실패 URL 재투입 (`/urls`)

실패 상태(`failed_transient`, `failed_permanent`, `dead`) URL 을 조회하고 재투입한다.

| 기능 | 경로 | 설명 |
|---|---|---|
| 전체 상태 요약 | `GET /urls` 상단 | 전체 status 건수 카드 (discovered / extracting / stored 는 정보 표시만) |
| 실패 URL 목록 | `GET /urls` 하단 | `failed_transient` / `failed_permanent` / `dead` 필터, source_type / host 추가 필터, 50건/페이지 |
| 단건 재투입 | `POST /urls/{id}/reinject` | `status=discovered`, `attempt_count=0`, error 컬럼 초기화 |
| 일괄 재투입 | `POST /urls/reinject-bulk` | 특정 실패 status 전체 재투입 |

**재투입 동작**: `status`, `attempt_count`, `last_error_code`, `last_error_msg`, `next_retry_at` 초기화. extraction-worker 가 다음 루프에서 자동 처리.

> 상단 카드 중 `failed_transient` / `failed_permanent` / `dead` 만 클릭 시 해당 status 필터가 적용된다. `discovered` / `extracting` / `stored` 카드는 현황 표시 전용이며 클릭해도 목록이 변하지 않는다.

### 3.4 도메인 규칙 관리 (`/domains`)

| 기능 | 경로 | 설명 |
|---|---|---|
| 목록 조회 | `GET /domains` | host 검색, `recent_fail_count` 내림차순 |
| 규칙 활성/비활성 | `POST /domains/{host}/toggle-rules` | `rules_enabled` 토글 |
| 쿨다운 해제 | `POST /domains/{host}/clear-cooldown` | `cooldown_until = NULL`, `recent_fail_count = 0` |
| 규칙 편집 | `POST /domains/{host}/edit-rules` | `rules_json` JSON 편집 + `rules_version` 자동 증가 |

규칙 편집 시 저장 전 JSON 유효성 검증. 실패 시 플래시 메시지.
저장된 규칙은 extraction-worker 가 TTL 캐시(기본 60초)로 자동 반영.

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
  tmpl.py              # Jinja2Templates 인스턴스 (순환 import 방지용 분리)

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
    keywords/list.html, form.html
    urls/list.html
    domains/list.html
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
| 템플릿 | Jinja2 3.1 |
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
| `RDS_CRAWLER_DB` | (필수) | 접속 스키마 (`crawlerdb`) |
| `TUNNEL_ENABLED` | `false` | SSH 터널 사용 여부 |
| `TUNNEL_SSH_HOST` | — | SSH 서버 호스트 |
| `TUNNEL_SSH_PORT` | `22` | SSH 서버 포트 |
| `TUNNEL_SSH_USER` | `ubuntu` | SSH 사용자 |
| `TUNNEL_SSH_KEY_PATH` | — | SSH 키 파일 경로 |
| `TUNNEL_LOCAL_PORT` | `13306` | 로컬 터널 포트 |
| `PORT` | `8000` | 웹 서버 포트 |
| `ADMIN_USER` | `admin` | 관리자 로그인 아이디 |
| `ADMIN_PASSWORD` | (필수) | 관리자 비밀번호 |
| `SESSION_SECRET` | (필수) | 세션 쿠키 서명 키 (운영 환경에서 반드시 교체) |
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
