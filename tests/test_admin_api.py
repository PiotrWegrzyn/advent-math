from tests.conftest import kid


def test_admin_endpoints_require_login(client):
    response = client.get("/api/admin/overview")

    assert response.status_code == 401


def test_wrong_admin_password_is_rejected(client):
    response = client.post("/api/admin/login", json={"password": "zle"})

    assert response.status_code == 401


def test_creating_class_generates_unique_codes_and_nicks(make_class):
    dashboard = make_class(size=25)

    students = dashboard["students"]
    assert [s["number"] for s in students] == list(range(1, 26))
    assert len({s["code"] for s in students}) == 25
    assert len({s["nick"] for s in students}) == 25
    assert all(len(s["code"]) == 6 and s["code"].isdigit() for s in students)


def test_class_size_can_grow(client, admin, make_class):
    dashboard = make_class(size=2)

    response = client.patch(f"/api/admin/classes/{dashboard['id']}", json={"size": 4}, headers=admin)

    assert response.json()["size"] == 4


def test_class_size_cannot_shrink(client, admin, make_class):
    dashboard = make_class(size=3)

    response = client.patch(f"/api/admin/classes/{dashboard['id']}", json={"size": 2}, headers=admin)

    assert response.status_code == 422


def test_duplicate_class_name_is_rejected(client, admin, make_class):
    make_class(name="6b")

    response = client.post("/api/admin/classes", json={"name": "6b", "task_set": "simple", "size": 1}, headers=admin)

    assert response.status_code == 409


def test_unknown_task_set_is_rejected(client, admin):
    response = client.post("/api/admin/classes", json={"name": "4c", "task_set": "nope", "size": 1}, headers=admin)

    assert response.status_code == 422


def test_deactivated_student_cannot_log_in_and_leaves_rankings(client, admin, make_class):
    student = make_class(size=2)["students"][0]

    client.patch(f"/api/admin/students/{student['id']}", json={"active": False}, headers=admin)

    assert client.get("/api/me", headers=kid(student["code"])).status_code == 401
    nicks = [r["nick"] for r in client.get("/api/admin/rankings", headers=admin).json()["school"]]
    assert student["nick"] not in nicks


def test_nick_must_be_unique(client, admin, make_class):
    first, second = make_class(size=2)["students"]

    response = client.patch(f"/api/admin/students/{second['id']}", json={"nick": first["nick"]}, headers=admin)

    assert response.status_code == 409


def test_dashboard_counts_opened_and_solved(client, admin, make_class):
    dashboard = make_class(size=2)
    first, second = dashboard["students"]
    client.post("/api/days/1/open", headers=kid(first["code"]))
    client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(first["code"]))
    client.post("/api/days/1/open", headers=kid(second["code"]))

    response = client.get(f"/api/admin/classes/{dashboard['id']}/dashboard", headers=admin)

    data = response.json()
    assert data["per_day"][0] == {"day": 1, "opened": 2, "solved": 1}
    assert [(s["opened"], s["solved"], s["points"]) for s in data["students"]] == [(1, 1, 100), (1, 0, 0)]


def test_class_ranking_uses_average_points(client, admin, make_class):
    big = make_class(name="4a", size=2)["students"]
    small = make_class(name="4b", size=1)["students"]
    for student in (big[0], small[0]):
        client.post("/api/days/1/open", headers=kid(student["code"]))
        client.post("/api/days/1/answer", json={"answer": "4"}, headers=kid(student["code"]))

    response = client.get("/api/admin/rankings", headers=admin)

    classes = response.json()["classes"]
    assert [(c["class_name"], c["average_points"]) for c in classes] == [("4b", 100.0), ("4a", 50.0)]


def test_cards_contain_qr_with_code_link(client, admin, make_class):
    dashboard = make_class(size=1)

    response = client.get(f"/api/admin/classes/{dashboard['id']}/cards", headers=admin)

    card = response.json()["cards"][0]
    assert card["url"].endswith(f"/#k={dashboard['students'][0]['code']}")
    assert card["qr_svg"].startswith("<svg")


def test_real_task_sets_cover_every_day():
    from app.config import DEFAULT_TASK_SETS_DIR
    from app.task_sets import load_task_sets

    task_sets = load_task_sets(DEFAULT_TASK_SETS_DIR)

    assert task_sets
    assert all(set(ts.days) == set(range(1, 25)) for ts in task_sets.values())
