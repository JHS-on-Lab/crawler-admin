"""FastAPI 앱 팩토리."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.middleware import RequireLoginMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.repository import db
    db.startup()
    yield
    db.shutdown()


def create_app() -> FastAPI:
    application = FastAPI(title="Crawler Admin", lifespan=lifespan)

    # 미들웨어 — 추가 역순으로 실행되므로 Session이 먼저, Auth가 나중
    application.add_middleware(RequireLoginMiddleware)
    application.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, max_age=86400)

    from app.routes import auth, dashboard, keywords, urls, domains, logs
    application.include_router(auth.router)
    application.include_router(dashboard.router)
    application.include_router(keywords.router)
    application.include_router(urls.router)
    application.include_router(domains.router)
    application.include_router(logs.router)

    return application


app = create_app()
