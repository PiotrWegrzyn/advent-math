import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEMO_TASK_SETS_DIR = Path(__file__).parent / "task_sets"


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./adwent.db"
    admin_password: str = ""
    secret_key: str = "dev-secret-change-me"
    start_date: date = date(2026, 12, 1)
    days: int = 24
    fake_now: str | None = None
    public_url: str | None = None
    unlock_all_days: bool = False
    seed_task_sets_dir: Path | None = DEMO_TASK_SETS_DIR


def load_settings() -> Settings:
    env = os.environ
    return Settings(
        database_url=env.get("DATABASE_URL", Settings.database_url),
        admin_password=env.get("ADMIN_PASSWORD", ""),
        secret_key=env.get("SECRET_KEY", Settings.secret_key),
        start_date=date.fromisoformat(env.get("START_DATE", Settings.start_date.isoformat())),
        days=int(env.get("DAYS", Settings.days)),
        fake_now=env.get("FAKE_NOW") or None,
        public_url=env.get("PUBLIC_URL") or None,
        unlock_all_days=env.get("UNLOCK_ALL_DAYS", "").lower() in {"1", "true", "yes"},
        seed_task_sets_dir=seed_dir(env.get("SEED_TASK_SETS_DIR")),
    )


def seed_dir(raw: str | None) -> Path | None:
    if raw is None:
        return DEMO_TASK_SETS_DIR
    return Path(raw) if raw.strip() else None
