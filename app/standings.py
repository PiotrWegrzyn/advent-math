from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from app.clock import from_db
from app.models import Student

TOP_TODAY = 10


def totals(student: Student) -> dict[str, int]:
    solved = [p for p in student.progress if p.solved_at is not None]
    return {
        "points": sum(p.points or 0 for p in solved),
        "solved": len(solved),
        "opened": len(student.progress),
    }


def solve_seconds(student: Student, day: int) -> int | None:
    for progress in student.progress:
        if progress.day == day and progress.solved_at is not None:
            return int((from_db(progress.solved_at) - from_db(progress.opened_at)).total_seconds())
    return None


def ranked(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
    result = []
    previous_key = None
    rank = 0
    for position, row in enumerate(rows, start=1):
        current = key(row)
        if current != previous_key:
            rank = position
            previous_key = current
        result.append({**row, "rank": rank})
    return result


def build_rankings(students: Iterable[Student], today: int, me: Student | None = None) -> dict[str, Any]:
    active = [s for s in students if s.active]
    rows = []
    for student in active:
        rows.append(
            {
                "nick": student.nick,
                "class_id": student.class_id,
                "class_name": student.school_class.name,
                "me": me is not None and student.id == me.id,
                **totals(student),
            }
        )

    rows.sort(key=lambda r: (-r["points"], -r["solved"], r["nick"]))
    school = ranked(rows, key=lambda r: (r["points"], r["solved"]))

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["class_id"]].append(row)

    class_rows = []
    for class_id, members in grouped.items():
        total = sum(m["points"] for m in members)
        class_rows.append(
            {
                "class_name": members[0]["class_name"],
                "students": len(members),
                "total_points": total,
                "average_points": round(total / len(members), 1),
                "mine": me is not None and class_id == me.class_id,
            }
        )
    class_rows.sort(key=lambda r: (-r["average_points"], r["class_name"]))
    classes = ranked(class_rows, key=lambda r: r["average_points"])

    fastest = []
    for student in active:
        seconds = solve_seconds(student, today)
        if seconds is not None:
            fastest.append(
                {
                    "nick": student.nick,
                    "class_name": student.school_class.name,
                    "seconds": seconds,
                    "me": me is not None and student.id == me.id,
                }
            )
    fastest.sort(key=lambda r: (r["seconds"], r["nick"]))
    today_top = ranked(fastest, key=lambda r: r["seconds"])[:TOP_TODAY]

    result: dict[str, Any] = {"school": school, "classes": classes, "today": today_top}
    if me is not None:
        result["my_class"] = ranked(
            [r for r in rows if r["class_id"] == me.class_id], key=lambda r: (r["points"], r["solved"])
        )
    for section in ("school", "my_class"):
        for row in result.get(section, []):
            row.pop("class_id", None)
    return result
