from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(timezone.utc)


def shifted_clock(fake_now: str) -> Clock:
    """Clock that starts at fake_now (Warsaw time) and keeps ticking."""
    target = datetime.fromisoformat(fake_now)
    if target.tzinfo is None:
        target = target.replace(tzinfo=WARSAW)
    offset = target - system_clock()
    return lambda: system_clock() + offset


def to_db(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def from_db(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc)


def day_index(now: datetime, start_date: date) -> int:
    return (now.astimezone(WARSAW).date() - start_date).days + 1


def iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
