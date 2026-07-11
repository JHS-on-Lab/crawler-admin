# crawler-admin 운영 명령어 가이드

## 구조 이해

```
crawler-admin
──────────────────────────────────────────
브라우저로 접속하는 내부 관리 웹 앱.
discovery-worker / extraction-worker 와 동일한 MySQL DB 를 공유한다.

주요 작업:
  키워드 등록 / 수정 / 활성화     → t_keyword
  URL 실패 모니터링 / 재투입      → t_crawl_url
  도메인 규칙 편집 / 쿨다운 해제  → t_domain
  수집 이력 조회                   → t_collection_log
```

---

## 1. 로컬 실행

```bash
# 기본 실행 (APP_ENV=local → .env.local 로드)
APP_ENV=local python -m app

# 포트 지정
APP_ENV=local python -m app --port 8080

# 도움말
python -m app --help
```

브라우저에서 `http://localhost:8000` 접속 후 `.env.local` 의 `ADMIN_USER` / `ADMIN_PASSWORD` 로 로그인.

같은 클라이언트 IP에서 15분 내 로그인 5회 실패하면 일시적으로 잠긴다(429). 프로세스를 재시작하면 풀린다.

---

## 2. Docker 빌드 및 실행

```bash
# 이미지 빌드
./deploy/build.sh

# 버전 태그 지정
./deploy/build.sh v1.0.0

# 컨테이너 실행 (APP_ENV=dev → .env.dev 파일 필요)
APP_ENV=dev ./deploy/run.sh

# 포트 변경 (기본 8000)
PORT=8080 APP_ENV=dev ./deploy/run.sh
```

```bash
# 로그 확인
docker logs -f crawler-admin

# 상태 확인
docker ps | grep crawler-admin

# 중지
docker stop crawler-admin
```

---

## 3. 환경변수 (`.env`)

```dotenv
# DB 접속 (discovery-worker / extraction-worker 와 동일한 RDS)
RDS_HOST=
RDS_PORT=3306
RDS_USER=
RDS_PASSWORD=
RDS_CRAWLER_DB=crawlerdb

# SSH 터널 (로컬에서 RDS 직접 접근 시)
TUNNEL_ENABLED=true
TUNNEL_SSH_HOST=
TUNNEL_SSH_USER=ubuntu
TUNNEL_SSH_KEY_PATH=
TUNNEL_LOCAL_PORT=13306

# 웹 서버
PORT=8000

# 관리자 계정
ADMIN_USER=admin
ADMIN_PASSWORD=

# 세션 쿠키 서명 키 — 운영 환경에서 반드시 교체
SESSION_SECRET=

# 로깅
LOG_DIR=./logs
LOG_LEVEL=INFO
LOG_ROTATION=daily     # daily | size
LOG_RETAIN_DAYS=30     # daily 모드: 보관 일수
LOG_BACKUP_COUNT=10    # size 모드: 보관 파일 수
```

---

## 4. 주요 기능별 사용법

### 키워드 즉시 수집 예약

웹 UI의 키워드 목록 → "즉시 수집" 버튼.
`next_discover_at = NULL` 로 업데이트되며 discovery-worker 의 다음 루프에서 처리된다.

### URL 재투입

**단건**: URL 목록 → 해당 행의 "재투입" 버튼.

**일괄**: URL 목록 상단 "일괄 재투입" → status 선택 → 확인.
`status = discovered`, `attempt_count = 0`, error 컬럼 초기화.

두 경우 모두 대상이 실패 상태(`failed_transient`/`failed_permanent`/`dead`)일 때만
서버가 실제로 갱신한다 — 이미 완료/처리 중인 URL은 재투입되지 않고 실패 메시지가 뜬다.

### 도메인 쿨다운 해제

도메인 목록 → 쿨다운 중인 도메인의 "쿨다운 해제" 버튼.
`cooldown_until = NULL`, `recent_fail_count = 0` 초기화.
extraction-worker 가 즉시 해당 도메인 URL 을 다시 처리한다.

### 도메인 규칙 편집

도메인 목록 → 도메인 행의 "규칙 편집" → JSON 직접 수정 → 저장.
저장 전 JSON 유효성 자동 검증. extraction-worker 가 TTL 캐시 만료(기본 60초) 후 자동 반영.

규칙 JSON 형식:
```json
{
  "title":        {"css": "h1.article-title"},
  "body":         {"css": "div.article-body"},
  "published_at": {"css": "span.date", "date_format": "%Y.%m.%d %H:%M"},
  "min_body_len": 100
}
```

자세한 규칙 문법은 `extraction-worker/docs/domain-rule-guide.md` 참조.

---

## 5. 상태 확인 (SQL)

```sql
-- 전체 URL 상태 현황
SELECT status, COUNT(*) AS cnt
FROM t_crawl_url
GROUP BY status
ORDER BY FIELD(status,
    'discovered','extracting','stored',
    'failed_transient','failed_permanent','dead');

-- 소스별 실패 현황
SELECT source_type, status, COUNT(*) AS cnt
FROM t_crawl_url
WHERE status IN ('failed_transient', 'failed_permanent', 'dead')
GROUP BY source_type, status
ORDER BY source_type, cnt DESC;

-- 오늘 수집 이력 요약
SELECT run_type, source_type,
       COUNT(*) AS runs,
       SUM(urls_found) AS found,
       SUM(urls_success) AS success,
       SUM(urls_failed) AS failed
FROM t_collection_log
WHERE run_date = CURDATE()
GROUP BY run_type, source_type
ORDER BY run_type, source_type;

-- 키워드별 수집 예약 현황
SELECT source_type, COUNT(*) AS total,
       SUM(enabled) AS enabled_cnt,
       SUM(next_discover_at IS NULL OR next_discover_at <= NOW()) AS due_now
FROM t_keyword
GROUP BY source_type;

-- 쿨다운 중인 도메인
SELECT host, cooldown_until, recent_fail_count
FROM t_domain
WHERE cooldown_until > NOW()
ORDER BY cooldown_until DESC;
```

---

## 6. 로그 확인

```bash
# 전체 로그 (tail)
tail -f logs/admin.log

# 에러 로그만
tail -f logs/admin-error.log
```
