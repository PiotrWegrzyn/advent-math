import pytest

from tests.conftest import kid


@pytest.fixture
def unlock_all_days() -> bool:
    return True


@pytest.fixture(autouse=True)
def before_start(clock):
    clock.set_local(2026, 11, 14)


def test_every_window_is_available_before_start(client, make_class):
    student = make_class(size=1)["students"][0]

    response = client.get("/api/me", headers=kid(student["code"]))

    data = response.json()
    assert data["unlocked"] is True
    assert data["phase"] == "running"
    assert [d["status"] for d in data["days"]] == ["available", "available", "available"]


def test_any_day_can_be_solved(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/3/open", headers=headers)

    response = client.post("/api/days/3/answer", json={"answer": "-3"}, headers=headers)

    assert response.json()["correct"] is True


def test_solved_window_can_be_reopened(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/2/open", headers=headers)
    client.post("/api/days/2/answer", json={"answer": "2,5"}, headers=headers)

    response = client.post("/api/days/2/open", headers=headers)

    assert response.json()["solved"] is True


def test_days_outside_calendar_stay_closed(client, make_class):
    student = make_class(size=1)["students"][0]

    response = client.post("/api/days/4/open", headers=kid(student["code"]))

    assert response.status_code == 403


def solve(client, headers, day, answer):
    client.post(f"/api/days/{day}/open", headers=headers)
    client.post(f"/api/days/{day}/answer", json={"answer": answer}, headers=headers)


def test_solved_windows_show_as_solved(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    solve(client, headers, 2, "2,5")

    response = client.get("/api/me", headers=headers)

    assert [d["status"] for d in response.json()["days"]] == ["available", "solved", "available"]


def test_header_streak_counts_run_ending_at_last_solved_day(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    solve(client, headers, 1, "4")
    solve(client, headers, 2, "2,5")

    response = client.get("/api/me", headers=headers)

    assert response.json()["streak"] == 2
    assert response.json()["today_multiplier"] == 1.21


def test_answer_can_be_revealed_in_test_mode(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/3/open", headers=headers)

    response = client.get("/api/days/3/reveal", headers=headers)

    assert response.json() == {"answer": "-3"}
