"""DB 연결 관리 — 앱 시작 시 엔진 초기화, 요청마다 커넥션 제공."""

from __future__ import annotations

from sqlalchemy import create_engine, Engine
from sqlalchemy.engine import URL

from app import config

_engine: Engine | None = None
_tunnel = None


def startup() -> None:
    global _engine, _tunnel

    host = config.RDS_HOST
    port = config.RDS_PORT

    if config.TUNNEL_ENABLED:
        from sshtunnel import SSHTunnelForwarder
        _tunnel = SSHTunnelForwarder(
            (config.TUNNEL_SSH_HOST, config.TUNNEL_SSH_PORT),
            ssh_username=config.TUNNEL_SSH_USER,
            ssh_pkey=config.TUNNEL_SSH_KEY_PATH,
            remote_bind_address=(config.RDS_HOST, config.RDS_PORT),
            local_bind_address=("127.0.0.1", config.TUNNEL_LOCAL_PORT),
        )
        _tunnel.start()
        host = "127.0.0.1"
        port = config.TUNNEL_LOCAL_PORT

    # URL.create() 는 username/password 를 자동으로 URL-encoding 한다.
    # f-string 조립은 비밀번호에 '@' 같은 특수문자가 있으면 DSN 파싱 자체가
    # 깨져서 기동에 실패한다(재현 확인됨).
    dsn = URL.create(
        "mysql+pymysql",
        username=config.RDS_USER,
        password=config.RDS_PASSWORD,
        host=host,
        port=port,
        database=config.RDS_CRAWLER_DB,
        query={"charset": "utf8mb4"},
    )
    _engine = create_engine(dsn, pool_pre_ping=True, pool_recycle=1800)


def shutdown() -> None:
    global _engine, _tunnel
    if _engine:
        _engine.dispose()
        _engine = None
    if _tunnel:
        _tunnel.stop()
        _tunnel = None


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("DB 엔진이 초기화되지 않았습니다.")
    return _engine
