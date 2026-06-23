"""
로깅 골격 — rescrape-dispatcher 와 동일한 패턴.

스트림 분리:
  admin.log        — INFO 이상
  admin-error.log  — WARNING 이상
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from app import config

_initialized = False


class _MergingAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs["extra"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


def setup(component: str) -> logging.Logger:
    global _initialized

    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    if not _initialized:
        _configure_root(log_dir)
        _initialized = True

    return logging.getLogger(component)


class _ContextFilter(logging.Filter):
    _DEFAULTS = {"component": "app", "phase": "-"}

    def filter(self, record: logging.LogRecord) -> bool:
        for key, val in self._DEFAULTS.items():
            if not hasattr(record, key):
                setattr(record, key, val)
        return True


_FMT = "%(asctime)s %(levelname)-5s [%(component)s] %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _make_handler(path: Path, level: int) -> logging.Handler:
    if config.LOG_ROTATION == "daily":
        h: logging.Handler = logging.handlers.TimedRotatingFileHandler(
            path, when="midnight", backupCount=config.LOG_RETAIN_DAYS, encoding="utf-8", utc=True
        )
    else:
        h = logging.handlers.RotatingFileHandler(
            path, maxBytes=100 * 1024 * 1024, backupCount=config.LOG_BACKUP_COUNT, encoding="utf-8"
        )
    h.setLevel(level)
    return h


def _configure_root(log_dir: Path) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    for lib in ("uvicorn.access", "sqlalchemy.pool", "sqlalchemy.engine",
                "paramiko", "pymysql"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    ctx = _ContextFilter()
    fmt = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    app_h = _make_handler(log_dir / "admin.log", logging.INFO)
    app_h.addFilter(ctx)
    app_h.setFormatter(fmt)
    root.addHandler(app_h)

    err_h = _make_handler(log_dir / "admin-error.log", logging.WARNING)
    err_h.addFilter(ctx)
    err_h.setFormatter(fmt)
    root.addHandler(err_h)

    console = logging.StreamHandler()
    console.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    console.addFilter(ctx)
    console.setFormatter(fmt)
    root.addHandler(console)
