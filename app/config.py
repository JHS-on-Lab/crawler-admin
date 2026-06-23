"""
환경변수에서 설정을 읽는다.

.env (공통 기본값) → .env.{APP_ENV} 순서로 로드하며 나중 파일이 앞 파일을 override 한다.
필수 변수가 없으면 validate() 가 오류를 출력하고 sys.exit(1).
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")
_app_env = os.getenv("APP_ENV", "local")
load_dotenv(_root / f".env.{_app_env}", override=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


# SSH Tunnel
TUNNEL_ENABLED      = _env_bool("TUNNEL_ENABLED")
TUNNEL_SSH_HOST     = _env("TUNNEL_SSH_HOST")
TUNNEL_SSH_PORT     = _env_int("TUNNEL_SSH_PORT", 22)
TUNNEL_SSH_USER     = _env("TUNNEL_SSH_USER", "ubuntu")
TUNNEL_SSH_KEY_PATH = _env("TUNNEL_SSH_KEY_PATH")
TUNNEL_LOCAL_PORT   = _env_int("TUNNEL_LOCAL_PORT", 13306)

# RDS
RDS_HOST        = _env("RDS_HOST")
RDS_PORT        = _env_int("RDS_PORT", 3306)
RDS_USER        = _env("RDS_USER")
RDS_PASSWORD    = _env("RDS_PASSWORD")
RDS_CRAWLER_DB  = _env("RDS_CRAWLER_DB")

# Web
PORT = _env_int("PORT", 8000)

# Auth
ADMIN_USER     = _env("ADMIN_USER", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "")
SESSION_SECRET = _env("SESSION_SECRET", "change-me")

# Logging
LOG_DIR          = _env("LOG_DIR", "./logs")
LOG_LEVEL        = _env("LOG_LEVEL", "INFO")
LOG_ROTATION     = _env("LOG_ROTATION", "daily")
LOG_RETAIN_DAYS  = _env_int("LOG_RETAIN_DAYS", 30)
LOG_BACKUP_COUNT = _env_int("LOG_BACKUP_COUNT", 10)


# ---------------------------------------------------------------------------
# 시작 시 검증
# ---------------------------------------------------------------------------

_REQUIRED = ["RDS_HOST", "RDS_USER", "RDS_PASSWORD", "RDS_CRAWLER_DB", "ADMIN_PASSWORD"]
_REQUIRED_TUNNEL = ["TUNNEL_SSH_HOST", "TUNNEL_SSH_KEY_PATH"]


def validate() -> None:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if TUNNEL_ENABLED:
        missing += [k for k in _REQUIRED_TUNNEL if not os.getenv(k)]

    if not missing:
        return

    print("ERROR: 다음 필수 환경변수가 설정되지 않았습니다:", file=sys.stderr)
    for key in missing:
        print(f"  - {key}", file=sys.stderr)
    print("  .env 파일 또는 환경변수를 확인하세요.", file=sys.stderr)
    sys.exit(1)
