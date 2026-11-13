from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from app import admin_api, kid_api
from app.clock import Clock, shifted_clock, system_clock
from app.config import Settings, load_settings
from app.context import AppContext
from app.db import make_engine
from app.models import Base
from app.security import AdminTokens
from app.task_sets import load_task_sets

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or load_settings()
    if clock is None:
        clock = shifted_clock(settings.fake_now) if settings.fake_now else system_clock

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)

    task_sets = load_task_sets(settings.task_sets_dir)
    missing = [day for ts in task_sets.values() for day in range(1, settings.days + 1) if day not in ts.days]
    if missing:
        raise ValueError(f"W zestawach zadań brakuje dni: {sorted(set(missing))}")

    app = FastAPI(title="Kalendarz adwentowy", docs_url=None, redoc_url=None)
    app.state.ctx = AppContext(
        settings=settings,
        engine=engine,
        sessions=sessionmaker(engine, expire_on_commit=False),
        clock=clock,
        task_sets=task_sets,
        admin_tokens=AdminTokens(settings.secret_key, settings.admin_password),
    )
    app.include_router(kid_api.router)
    app.include_router(admin_api.router)

    @app.get("/admin", include_in_schema=False)
    def admin_redirect():
        return RedirectResponse("/admin.html")

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True}

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
