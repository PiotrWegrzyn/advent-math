import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import add_missing_columns, make_engine
from app.models import Base
from app.task_sets import TaskSetError, load_task_sets, parse_task_set, save_task_set

RECTANGLE = '<svg viewBox="0 0 100 60"><rect x="5" y="5" width="90" height="50" fill="none" stroke="#000"/></svg>'


def task_set_with_image(image: str) -> dict:
    return {"name": "Klasa 6", "days": {"1": [{"text": "Oblicz pole.", "answer": "15", "image": image}]}}


def test_image_is_kept_through_database():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    task_set = parse_task_set("k6", task_set_with_image(RECTANGLE), days=1)

    with Session(engine) as session, session.begin():
        save_task_set(session, task_set)
    with Session(engine) as session:
        loaded = load_task_sets(session)

    assert loaded["k6"].days[1][0].image == RECTANGLE


def test_variant_without_image_has_none():
    data = {"name": "Klasa 6", "days": {"1": [{"text": "2 + 2", "answer": "4"}]}}

    task_set = parse_task_set("k6", data, days=1)

    assert task_set.days[1][0].image is None


@pytest.mark.parametrize(
    "image",
    [
        "<rect/>",
        '<svg><script>alert(1)</script></svg>',
        '<svg onload="alert(1)"></svg>',
        '<svg><a href="https://example.com"><text>x</text></a></svg>',
        '<svg><image href="https://example.com/x.png"/></svg>',
    ],
)
def test_unsafe_or_invalid_images_are_rejected(image):
    data = task_set_with_image(image)

    with pytest.raises(TaskSetError, match="rysunek"):
        parse_task_set("k6", data, days=1)


def test_missing_image_column_is_added_to_existing_table():
    engine = make_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE task_variants (id INTEGER PRIMARY KEY, text TEXT)"))

    add_missing_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("task_variants")}
    assert "image" in columns


def test_open_returns_image(client, make_class, admin):
    student = make_class(size=1)["students"][0]

    response = client.post("/api/days/1/open", headers={"X-Code": student["code"]})

    assert "image" in response.json()
    assert response.json()["image"] is None
