import json
from dataclasses import dataclass
from pathlib import Path

from app.answers import parse_answer


@dataclass(frozen=True)
class Variant:
    text: str
    answer: str


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


def load_task_set(path: Path) -> TaskSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    days: dict[int, list[Variant]] = {}
    for day, variants in data["days"].items():
        parsed = [Variant(text=v["text"], answer=str(v["answer"])) for v in variants]
        if not parsed:
            raise ValueError(f"{path.name}: dzień {day} nie ma żadnego zadania")
        for variant in parsed:
            if parse_answer(variant.answer) is None:
                raise ValueError(f"{path.name}: dzień {day}: niepoprawna odpowiedź {variant.answer!r}")
        days[int(day)] = parsed
    return TaskSet(key=path.stem, name=data["name"], days=days)


def load_task_sets(directory: Path) -> dict[str, TaskSet]:
    return {path.stem: load_task_set(path) for path in sorted(directory.glob("*.json"))}
