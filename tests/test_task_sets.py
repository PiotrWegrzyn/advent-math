import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import make_engine
from app.import_tasks import main as import_main
from app.models import Base, TaskVariantRecord
from app.task_sets import TaskSetError, TaskSetStore, load_task_sets, parse_task_set, save_task_set


def task_set_data(days: int = 2, answer: str = "4") -> dict:
    return {"name": "Klasa 7", "days": {str(d): [{"text": f"Zadanie {d}", "answer": answer}] for d in range(1, days + 1)}}


@pytest.fixture
def engine():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def test_parse_rejects_missing_day():
    data = task_set_data(days=1)

    with pytest.raises(TaskSetError, match=r"brakuje dni \[2\]"):
        parse_task_set("k7", data, days=2)


def test_parse_rejects_day_out_of_range():
    data = task_set_data(days=3)

    with pytest.raises(TaskSetError, match="poza zakresem"):
        parse_task_set("k7", data, days=2)


@pytest.mark.parametrize("answer", ["1/3", "", "abc", "2,5 zł"])
def test_parse_rejects_answer_child_cannot_type(answer):
    data = task_set_data(answer=answer)

    with pytest.raises(TaskSetError, match="niepoprawna odpowiedź"):
        parse_task_set("k7", data, days=2)


def test_parse_accepts_decimal_comma_and_minus():
    data = {"name": "X", "days": {"1": [{"text": "a", "answer": "-2,5"}], "2": [{"text": "b", "answer": 7}]}}

    task_set = parse_task_set("k7", data, days=2)

    assert [v.answer for v in task_set.days[1] + task_set.days[2]] == ["-2,5", "7"]


def test_save_replaces_whole_set(engine):
    first = parse_task_set("k7", task_set_data(), days=2)
    second = parse_task_set("k7", {"name": "Klasa 7 v2", "days": {"1": [{"text": "a", "answer": "1"}, {"text": "b", "answer": "2"}], "2": [{"text": "c", "answer": "3"}]}}, days=2)
    with Session(engine) as session, session.begin():
        save_task_set(session, first)
    with Session(engine) as session, session.begin():
        save_task_set(session, second)

    with Session(engine) as session:
        loaded = load_task_sets(session)
        variant_count = session.scalar(select(func.count()).select_from(TaskVariantRecord))

    assert loaded == {"k7": second}
    assert variant_count == 3


def test_store_reloads_after_ttl(engine):
    sessions = sessionmaker(engine)
    now = [0.0]
    store = TaskSetStore(sessions, ttl=30, now=lambda: now[0])
    list(store)
    with Session(engine) as session, session.begin():
        save_task_set(session, parse_task_set("k7", task_set_data(), days=2))

    before = list(store)
    now[0] = 31
    after = list(store)

    assert before == []
    assert after == ["k7"]


def test_import_command_loads_file_into_database(tmp_path, monkeypatch, capsys):
    db_url = f"sqlite:///{tmp_path / 'db.sqlite'}"
    path = tmp_path / "klasa7.json"
    path.write_text(json.dumps(task_set_data(days=24)), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", db_url)

    code = import_main([str(path)])

    with Session(make_engine(db_url)) as session:
        loaded = load_task_sets(session)
    assert code == 0
    assert set(loaded["klasa7"].days) == set(range(1, 25))
    assert "24 dni" in capsys.readouterr().out


def test_import_command_rejects_incomplete_set_without_touching_database(tmp_path, monkeypatch, capsys):
    db_url = f"sqlite:///{tmp_path / 'db.sqlite'}"
    path = tmp_path / "klasa7.json"
    path.write_text(json.dumps(task_set_data(days=23)), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", db_url)

    code = import_main([str(path)])

    assert code == 1
    assert "brakuje dni [24]" in capsys.readouterr().err
    assert not (tmp_path / "db.sqlite").exists()
