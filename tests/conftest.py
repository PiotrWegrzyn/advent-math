from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.clock import WARSAW
from app.config import Settings
from app.main import create_app

TASK_SETS_DIR = Path(__file__).parent / "task_sets"
ADMIN_PASSWORD = "sekret"


class FakeClock:
    def __init__(self, moment: datetime):
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs) -> None:
        self.moment += timedelta(**kwargs)

    def set_local(self, year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> None:
        self.moment = datetime(year, month, day, hour, minute, tzinfo=WARSAW)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 12, 1, 12, 0, tzinfo=WARSAW))


@pytest.fixture
def client(clock: FakeClock) -> TestClient:
    settings = Settings(
        database_url="sqlite://",
        admin_password=ADMIN_PASSWORD,
        secret_key="test",
        start_date=date(2026, 12, 1),
        days=3,
        seed_task_sets_dir=TASK_SETS_DIR,
    )
    return TestClient(create_app(settings, clock=clock))


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    token = client.post("/api/admin/login", json={"password": ADMIN_PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_class(client: TestClient, admin: dict[str, str]):
    def _make(name: str = "4a", size: int = 2) -> dict:
        created = client.post("/api/admin/classes", json={"name": name, "task_set": "simple", "size": size}, headers=admin)
        assert created.status_code == 200, created.text
        return client.get(f"/api/admin/classes/{created.json()['id']}/dashboard", headers=admin).json()

    return _make


def kid(code: str) -> dict[str, str]:
    return {"X-Code": code}
