import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.app_settings import TEST_MODE, read_flag, write_flag
from app.clock import Clock, day_index
from app.config import Settings
from app.security import AdminTokens, FailureLimiter
from app.task_sets import TaskSet


@dataclass
class AppContext:
    settings: Settings
    engine: Engine
    sessions: sessionmaker[Session]
    clock: Clock
    task_sets: Mapping[str, TaskSet]
    admin_tokens: AdminTokens
    login_limiter: FailureLimiter = field(default_factory=FailureLimiter)
    _test_mode: tuple[float, bool] | None = None

    def test_mode(self) -> bool:
        now = time.monotonic()
        if self._test_mode is None or now - self._test_mode[0] >= 5:
            with self.sessions() as session:
                self._test_mode = (now, bool(read_flag(session, TEST_MODE)))
        return self._test_mode[1]

    def set_test_mode(self, enabled: bool) -> None:
        with self.sessions() as session, session.begin():
            write_flag(session, TEST_MODE, enabled)
        self._test_mode = (time.monotonic(), enabled)

    def today(self) -> int:
        return day_index(self.clock(), self.settings.start_date)

    def phase(self) -> str:
        if self.test_mode():
            return "running"
        today = self.today()
        if today < 1:
            return "before"
        if today > self.settings.days:
            return "after"
        return "running"


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_session(request: Request) -> Iterator[Session]:
    with get_ctx(request).sessions() as session:
        yield session
