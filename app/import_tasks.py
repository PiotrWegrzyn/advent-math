import argparse
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import load_settings
from app.db import add_missing_columns, make_engine
from app.models import Base
from app.task_sets import TaskSetError, read_task_set_file, save_task_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wgrywa zestawy zadań z plików JSON do bazy.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--key", help="klucz zestawu (domyślnie nazwa pliku); tylko dla jednego pliku")
    args = parser.parse_args(argv)
    if args.key and len(args.files) > 1:
        parser.error("--key działa tylko z jednym plikiem")

    settings = load_settings()
    try:
        task_sets = [read_task_set_file(path, settings.days, args.key) for path in args.files]
    except (TaskSetError, OSError, ValueError) as error:
        print(f"Błąd: {error}", file=sys.stderr)
        return 1

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    with Session(engine) as session, session.begin():
        for task_set in task_sets:
            save_task_set(session, task_set)
    for task_set in task_sets:
        count = sum(len(v) for v in task_set.days.values())
        print(f"Zaimportowano „{task_set.name}” ({task_set.key}): {len(task_set.days)} dni, {count} wariantów")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
