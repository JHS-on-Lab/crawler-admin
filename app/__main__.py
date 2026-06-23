"""
crawler-admin 진입점.

실행 예:
  python -m app
  python -m app --port 8080
"""

from __future__ import annotations

import argparse

from app import config, logging_setup


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="crawler-admin")
    p.add_argument("--port", type=int, default=None, help="HTTP 포트 (기본: PORT 환경변수 또는 8000)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    config.validate()
    logging_setup.setup("main")

    import uvicorn
    from app.main import app

    port = args.port or config.PORT
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=config.LOG_LEVEL.lower())


if __name__ == "__main__":
    main()
