from tests.conftest import kid


def first_student(make_class) -> dict:
    return make_class(size=2)["students"][0]


def test_login_with_unknown_code_is_rejected(client):
    response = client.post("/api/login", json={"code": "000000"})

    assert response.status_code == 401


def test_login_accepts_code_with_spaces(client, make_class):
    student = first_student(make_class)

    response = client.post("/api/login", json={"code": f" {student['code'][:3]} {student['code'][3:]} "})

    assert response.status_code == 200
    assert response.json()["nick"] == student["nick"]


def test_calendar_shows_today_available_and_future_locked(client, make_class):
    student = first_student(make_class)

    response = client.get("/api/me", headers=kid(student["code"]))

    statuses = [d["status"] for d in response.json()["days"]]
    assert statuses == ["available", "locked", "locked"]


def test_before_start_every_door_is_locked(client, make_class, clock):
    student = first_student(make_class)
    clock.set_local(2026, 11, 30, 23, 59)

    response = client.post("/api/days/1/open", headers=kid(student["code"]))

    assert response.status_code == 403


def test_open_does_not_reveal_answer(client, make_class):
    student = first_student(make_class)

    response = client.post("/api/days/1/open", headers=kid(student["code"]))

    assert response.status_code == 200
    assert "answer" not in response.json()
    assert response.json()["text"] in {"2 + 2", "3 + 3"}


def test_neighbouring_students_get_different_variants(client, make_class):
    first, second = make_class(size=2)["students"]

    texts = {client.post("/api/days/1/open", headers=kid(s["code"])).json()["text"] for s in (first, second)}

    assert texts == {"2 + 2", "3 + 3"}


def test_correct_answer_within_five_minutes_gives_full_points(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    client.post("/api/days/1/open", headers=kid(student["code"]))
    clock.advance(minutes=4)

    response = client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(student["code"]))

    assert response.json()["correct"] is True
    assert response.json()["points"] == 100


def test_wrong_answers_and_time_reduce_points(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)
    client.post("/api/days/1/answer", json={"answer": "5"}, headers=headers)
    client.post("/api/days/1/answer", json={"answer": "6"}, headers=headers)
    clock.advance(minutes=6, seconds=30)

    response = client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)

    assert response.json()["points"] == 100 - 20 - 2


def test_invalid_answer_format_is_not_counted_as_attempt(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)

    response = client.post("/api/days/1/answer", json={"answer": "cztery"}, headers=headers)

    assert response.status_code == 422
    assert client.post("/api/days/1/open", headers=headers).json()["wrong_attempts"] == 0


def test_answer_without_opening_is_rejected(client, make_class):
    student = make_class(size=1)["students"][0]

    response = client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(student["code"]))

    assert response.status_code == 409


def test_solving_twice_does_not_add_points(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)

    response = client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)

    assert response.json()["already_solved"] is True
    assert client.get("/api/me", headers=headers).json()["total_points"] == 100


def test_streak_multiplies_next_day_points(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)
    clock.set_local(2026, 12, 2)
    client.post("/api/days/2/open", headers=headers)

    response = client.post("/api/days/2/answer", json={"answer": "2,5"}, headers=headers)

    assert response.json()["points"] == 110
    assert client.get("/api/me", headers=headers).json()["streak"] == 2


def test_missed_day_breaks_streak_and_cannot_be_caught_up(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)
    clock.set_local(2026, 12, 3)

    late = client.post("/api/days/2/open", headers=headers)
    client.post("/api/days/3/open", headers=headers)
    response = client.post("/api/days/3/answer", json={"answer": "-3"}, headers=headers)

    assert late.status_code == 403
    assert response.json()["points"] == 100
    statuses = [d["status"] for d in client.get("/api/me", headers=headers).json()["days"]]
    assert statuses == ["solved", "missed", "solved"]


def test_day_changes_at_midnight_warsaw_time(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    clock.set_local(2026, 12, 1, 23, 58)
    client.post("/api/days/1/open", headers=headers)
    clock.advance(minutes=3)

    response = client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers)

    assert response.status_code == 403


def test_regenerated_code_keeps_progress(client, make_class, admin):
    student = make_class(size=1)["students"][0]
    client.post("/api/days/1/open", headers=kid(student["code"]))
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(student["code"]))

    new_code = client.post(f"/api/admin/students/{student['id']}/regenerate-code", headers=admin).json()["code"]

    assert client.get("/api/me", headers=kid(student["code"])).status_code == 401
    assert client.get("/api/me", headers=kid(new_code)).json()["total_points"] == 100


def test_rankings_mark_current_student(client, make_class, clock):
    first, second = make_class(size=2)["students"]
    client.post("/api/days/1/open", headers=kid(first["code"]))
    clock.advance(seconds=40)
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(first["code"]))

    response = client.get("/api/rankings", headers=kid(second["code"]))

    data = response.json()
    assert [r["nick"] for r in data["my_class"]][0] == first["nick"]
    assert [r["me"] for r in data["my_class"]] == [False, True]
    assert data["today"] == [{"nick": first["nick"], "class_name": "4a", "seconds": 40, "me": False, "rank": 1}]
    assert "code" not in str(data)


def test_correct_answer_returns_breakdown_also_on_reopen(client, make_class, clock):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)
    client.post("/api/days/1/answer", json={"answer": "5"}, headers=headers)
    clock.advance(minutes=5, seconds=10)
    answered = client.post("/api/days/1/answer", json={"answer": "4"}, headers=headers).json()

    reopened = client.post("/api/days/1/open", headers=headers).json()

    assert answered["breakdown"]["started_minutes_over"] == 1
    assert answered["breakdown"]["wrong_attempts"] == 1
    assert answered["breakdown"]["points"] == answered["points"] == 89
    assert reopened["breakdown"] == answered["breakdown"]


def test_html_pages_are_revalidated(client):
    response = client.get("/")

    assert response.headers["cache-control"] == "no-cache"


def test_answer_cannot_be_revealed_outside_test_mode(client, make_class):
    student = make_class(size=1)["students"][0]
    headers = kid(student["code"])
    client.post("/api/days/1/open", headers=headers)

    response = client.get("/api/days/1/reveal", headers=headers)

    assert response.status_code == 404
    assert "answer" not in response.json()
