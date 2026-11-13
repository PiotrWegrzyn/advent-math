from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, sessionmaker

from app import admin_api, kid_api
from app.clock import Clock, shifted_clock, system_clock
from app.config import Settings, load_settings
from app.context import AppContext
from app.app_settings import TEST_MODE, read_flag, write_flag
from app.db import add_missing_columns, make_engine
from app.models import Base
from app.security import AdminTokens
from app.task_sets import TaskSetStore, seed_task_sets

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or load_settings()
    if clock is None:
        clock = shifted_clock(settings.fake_now) if settings.fake_now else system_clock

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    add_missing_columns(engine)

    with Session(engine) as session, session.begin():
        if read_flag(session, TEST_MODE) is None:
            write_flag(session, TEST_MODE, settings.unlock_all_days)
    if settings.seed_task_sets_dir is not None:
        with Session(engine) as session, session.begin():
            seed_task_sets(session, settings.seed_task_sets_dir, settings.days)
    sessions = sessionmaker(engine, expire_on_commit=False)

    app = FastAPI(title="Kalendarz adwentowy", docs_url=None, redoc_url=None)
    app.state.ctx = AppContext(
        settings=settings,
        engine=engine,
        sessions=sessions,
        clock=clock,
        task_sets=TaskSetStore(sessions),
        admin_tokens=AdminTokens(settings.secret_key, settings.admin_password),
    )
    @app.middleware("http")
    async def revalidate_html(request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(kid_api.router)
    app.include_router(admin_api.router)

    @app.get("/admin", include_in_schema=False)
    def admin_redirect():
        return RedirectResponse("/admin.html")

    @app.get("/health", include_in_schema=False)
    def health():
        return {"ok": True}

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
