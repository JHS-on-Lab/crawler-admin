# crawler-admin

`discovery-worker` / `extraction-worker` / `rescrape-dispatcher`로 구성된 크롤러
파이프라인을 운영하기 위한 내부 전용 FastAPI 관리자 웹앱이다. 별도 API 레이어 없이
워커들과 동일한 MySQL(`crawlerdb`)에 직접 붙어 서버 렌더링(Jinja2 + Bootstrap 5,
JS 빌드 없음) UI를 제공한다.

## 주요 기능

- **대시보드** (`/`) — `t_crawl_url` 상태 요약, 키워드 현황(소스별 전체/활성 수), 특정 날짜의
  수집/추출 일별 요약, 최근 7일 추출 실패율 추이 차트
- **키워드 관리** (`/keywords`) — CRUD, 활성/비활성, 즉시 수집 트리거, 키워드별 일별 통계, Excel 내보내기
- **실패 URL 관리** (`/urls`) — `failed_transient`/`failed_permanent`/`dead` URL 조회 및 단건/일괄 재투입
- **도메인 규칙 관리** (`/domains`) — 규칙 토글, 도메인 제외(차단) 토글, 신규 도메인 선제 차단,
  쿨다운 해제, `rules_json` 편집, 실패 도메인 규칙요청 텍스트 생성, Excel 내보내기
- **수집 이력** (`/logs`) — `t_collection_log` 필터 조회

단일 관리자 계정(`ADMIN_USER`/`ADMIN_PASSWORD`), 서명된 세션 쿠키(24h), 모든
state-changing POST에 CSRF 토큰, IP 기준 brute-force 잠금(15분 내 5회 실패 → 429)이
적용되어 있다. 자세한 설계는 [docs/crawler-admin-design.md](docs/crawler-admin-design.md),
운영 커맨드는 [docs/ops-commands.md](docs/ops-commands.md) 참고.

## 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 실행 방법

### 로컬

```bash
APP_ENV=local python -m app          # 기본 포트 8000
APP_ENV=local python -m app --port 8080   # 포트 지정
python -m app --help
```

시작 시 `config.validate()`가 필수 환경변수 누락이나 `SESSION_SECRET`이 플레이스홀더
그대로인 경우 에러 메시지를 출력하고 종료(exit 1)한다.

`http://localhost:8000` 접속 후 `ADMIN_USER`/`ADMIN_PASSWORD`로 로그인.

### CLI 인자

| 인자 | 설명 | 값 범위 | 기본값 |
|---|---|---|---|
| `--port` | uvicorn 리스닝 포트 (env `PORT`보다 우선) | 정수 | `PORT` env 값 또는 `8000` |

### Docker

```bash
./deploy/build.sh            # crawler-admin:latest 빌드
./deploy/build.sh v1.0.0     # 버전 태그 지정 (선택)

APP_ENV=dev ./deploy/run.sh          # 기본 APP_ENV=dev, 호스트에 .env.dev 필요
PORT=8080 APP_ENV=dev ./deploy/run.sh   # 호스트 포트 지정 (컨테이너 내부는 항상 8000)
```

Dockerfile에는 의도적으로 `CMD`/`ENTRYPOINT`가 없다 — 실행 커맨드는 항상
`deploy/run.sh`(`docker run ... --user "$(id -u):$(id -g)" ... crawler-admin:latest python -m app`)에서
주입한다. `run.sh`는 호스트 로그 디렉토리(`~/apps/data/crawler-admin/logs`)를 컨테이너의
`/app/logs`에 볼륨 마운트하므로, Docker로 띄운 경우 로그는 로컬 실행 시의 `./logs` 대신
이 호스트 경로에서 확인한다.

```bash
docker logs -f crawler-admin
docker ps | grep crawler-admin
docker stop crawler-admin
```

## 환경 변수

`.env`(공통 기본값) 로드 후 `.env.{APP_ENV}` 로 override(`APP_ENV` 기본값 `local`).
필수 항목 누락 또는 `SESSION_SECRET`이 플레이스홀더면 기동 시 검증 실패.

| 변수 | 설명 | 값 범위 / 형식 | 기본값 | 예시 |
|---|---|---|---|---|
| `APP_ENV` | `.env.{APP_ENV}` 오버레이 선택 | 임의 문자열 | `local` | `dev`, `prod` |
| `PORT` | uvicorn 포트 (`--port`로 override 가능) | 정수 | `8000` | `8000` |
| `RDS_HOST` | MySQL 호스트 (워커들과 공유) | 호스트명 | 없음 (**필수**) | `my-rds.ap-northeast-2.rds.amazonaws.com` |
| `RDS_PORT` | MySQL 포트 | 정수 | `3306` | `3306` |
| `RDS_USER` | MySQL 사용자 | 문자열 | 없음 (**필수**) | `admin` |
| `RDS_PASSWORD` | MySQL 비밀번호 | 문자열 | 없음 (**필수**) | - |
| `RDS_CRAWLER_DB` | 스키마 이름 | 문자열 | 없음 (**필수** — 코드 기본값은 빈 문자열, 배포용 `.env`가 `crawlerdb`로 세팅) | `crawlerdb` |
| `TUNNEL_ENABLED` | SSH 터널로 RDS 접속 여부 | `true`/`1`/`yes`(대소문자 무관) = true | `false` | `true` |
| `TUNNEL_SSH_HOST` | SSH bastion 호스트 | 호스트명 | 없음 (터널 활성 시 필수) | `bastion.example.com` |
| `TUNNEL_SSH_PORT` | SSH 포트 | 정수 | `22` | `22` |
| `TUNNEL_SSH_USER` | SSH 사용자 | 문자열 | `ubuntu` | `ubuntu` |
| `TUNNEL_SSH_KEY_PATH` | SSH 개인키 경로 | 파일 경로 | 없음 (터널 활성 시 필수) | `/home/user/.ssh/id_rsa` |
| `TUNNEL_LOCAL_PORT` | 터널 로컬 바인딩 포트 | 정수 | `13306` | `13306` |
| `ADMIN_USER` | 관리자 로그인 계정 | 문자열 | `admin` | `admin` |
| `ADMIN_PASSWORD` | 관리자 로그인 비밀번호 | 문자열 | 없음 (**필수**) | - |
| `SESSION_SECRET` | 세션 쿠키 서명 키 | 문자열, `change-me`/`change-me-in-production` 금지(둘 다 플레이스홀더로 검증 실패 유발) | 코드 기본값은 `change-me`, 배포용 `.env`는 `change-me-in-production`으로 override | 랜덤 긴 문자열 |
| `LOG_DIR` | 로그 파일 디렉토리 | 경로 | `./logs` | `./logs` |
| `LOG_LEVEL` | 루트 로거 레벨 (uvicorn에도 소문자로 전달) | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR`\|`CRITICAL` | `INFO` | `INFO` |
| `LOG_ROTATION` | 로그 로테이션 방식 | `daily`(자정 UTC 기준) \| `size`(100MB/파일) | `daily` | `daily` |
| `LOG_RETAIN_DAYS` | 보관 일수 (`daily` 모드에서만 사용) | 정수 | `30` | `30` |
| `LOG_BACKUP_COUNT` | 보관 파일 개수 (`size` 모드에서만 사용) | 정수 | `10` | `10` |

로그 출력: `{LOG_DIR}/admin.log`(INFO+), `{LOG_DIR}/admin-error.log`(WARNING+), 콘솔.

## 주요 스택

FastAPI, uvicorn, Jinja2, python-multipart(폼 파싱), SQLAlchemy + PyMySQL, sshtunnel/paramiko(SSH 터널),
itsdangerous(세션 서명), openpyxl(엑셀 내보내기). 프론트엔드는 CDN Bootstrap 5 +
Bootstrap Icons만 사용하며 별도 JS 빌드 과정은 없다.
