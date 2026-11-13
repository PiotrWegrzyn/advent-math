import json
import re
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.answers import parse_answer
from app.models import TaskSetRecord, TaskVariantRecord


@dataclass(frozen=True)
class Variant:
    text: str
    answer: str
    image: str | None = None


@dataclass(frozen=True)
class TaskSet:
    key: str
    name: str
    days: dict[int, list[Variant]]

    def variant_number(self, student_number: int, day: int) -> int:
        return (student_number + day - 2) % len(self.days[day])

    def variant(self, day: int, variant_number: int) -> Variant:
        variants = self.days[day]
        return variants[variant_number % len(variants)]


class TaskSetError(ValueError):
    pass


MAX_IMAGE_LENGTH = 100_000
UNSAFE_SVG = re.compile(r"<script|<foreignObject|\bon[a-z]+\s*=|javascript:|<image|href\s*=\s*[\"'](?!#)", re.IGNORECASE)


def parse_image(raw: object, where: str) -> str | None:
    if raw is None or raw == "":
        return None
    image = str(raw).strip()
    if not image.startswith("<svg") or not image.endswith("</svg>"):
        raise TaskSetError(f"{where}: rysunek musi być kodem SVG (<svg>…</svg>)")
    if len(image) > MAX_IMAGE_LENGTH:
        raise TaskSetError(f"{where}: rysunek jest za duży")
    if UNSAFE_SVG.search(image):
        raise TaskSetError(f"{where}: rysunek zawiera niedozwolone elementy (skrypty, linki, obrazy zewnętrzne)")
    return image


def parse_task_set(key: str, data: dict, days: int) -> TaskSet:
    name = str(data.get("name", "")).strip()
    if not name:
        raise TaskSetError(f"{key}: brak nazwy zestawu")
    parsed: dict[int, list[Variant]] = {}
    for raw_day, variants in data.get("days", {}).items():
        day = int(raw_day)
        if not 1 <= day <= days:
            raise TaskSetError(f"{key}: dzień {day} jest poza zakresem 1–{days}")
        if not variants:
            raise TaskSetError(f"{key}: dzień {day} nie ma żadnego zadania")
        parsed[day] = []
        for v in variants:
            text, answer = str(v.get("text", "")).strip(), str(v.get("answer", "")).strip()
            if not text:
                raise TaskSetError(f"{key}: dzień {day}: puste zadanie")
            if parse_answer(answer) is None:
                raise TaskSetError(f"{key}: dzień {day}: niepoprawna odpowiedź {answer!r}")
            image = parse_image(v.get("image"), f"{key}: dzień {day}")
            parsed[day].append(Variant(text=text, answer=answer, image=image))
    missing = [day for day in range(1, days + 1) if day not in parsed]
    if missing:
        raise TaskSetError(f"{key}: brakuje dni {missing}")
    return TaskSet(key=key, name=name, days=dict(sorted(parsed.items())))


def read_task_set_file(path: Path, days: int, key: str | None = None) -> TaskSet:
    return parse_task_set(key or path.stem, json.loads(path.read_text(encoding="utf-8")), days)


def save_task_set(session: Session, task_set: TaskSet) -> None:
    record = session.scalar(select(TaskSetRecord).where(TaskSetRecord.key == task_set.key))
    if record is None:
        record = TaskSetRecord(key=task_set.key, name=task_set.name)
        session.add(record)
    else:
        record.name = task_set.name
        record.variants.clear()
        session.flush()
    record.variants.extend(
        TaskVariantRecord(day=day, position=position, text=v.text, answer=v.answer, image=v.image)
        for day, variants in task_set.days.items()
        for position, v in enumerate(variants)
    )


def seed_task_sets(session: Session, directory: Path, days: int) -> None:
    existing = set(session.scalars(select(TaskSetRecord.key)))
    for path in sorted(directory.glob("*.json")):
        if path.stem not in existing:
            save_task_set(session, read_task_set_file(path, days))


def delete_task_set(session: Session, key: str) -> bool:
    record = session.scalar(select(TaskSetRecord).where(TaskSetRecord.key == key))
    if record is None:
        return False
    session.delete(record)
    return True


def load_task_sets(session: Session) -> dict[str, TaskSet]:
    records = session.scalars(
        select(TaskSetRecord).options(selectinload(TaskSetRecord.variants)).order_by(TaskSetRecord.key)
    )
    task_sets = {}
    for record in records:
        days: dict[int, list[Variant]] = {}
        for v in record.variants:
            days.setdefault(v.day, []).append(Variant(text=v.text, answer=v.answer, image=v.image))
        task_sets[record.key] = TaskSet(key=record.key, name=record.name, days=days)
    return task_sets


class TaskSetStore(Mapping[str, TaskSet]):
    def __init__(self, sessions: sessionmaker[Session], ttl: float = 30.0, now: Callable[[], float] = time.monotonic):
        self._sessions = sessions
        self._ttl = ttl
        self._now = now
        self._cache: dict[str, TaskSet] | None = None
        self._loaded_at = 0.0

    def _sets(self) -> dict[str, TaskSet]:
        if self._cache is None or self._now() - self._loaded_at >= self._ttl:
            with self._sessions() as session:
                self._cache = load_task_sets(session)
            self._loaded_at = self._now()
        return self._cache

    def invalidate(self) -> None:
        self._cache = None

    def __getitem__(self, key: str) -> TaskSet:
        return self._sets()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._sets())

    def __len__(self) -> int:
        return len(self._sets())
