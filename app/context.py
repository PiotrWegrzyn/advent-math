from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

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

    def today(self) -> int:
        return day_index(self.clock(), self.settings.start_date)

    def phase(self) -> str:
        if self.settings.unlock_all_days:
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
