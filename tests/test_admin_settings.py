from tests.conftest import kid


def test_test_mode_is_off_by_default(client, admin):
    response = client.get("/api/admin/overview", headers=admin)

    assert response.json()["test_mode"] is False


def test_admin_can_turn_test_mode_on(client, admin, make_class, clock):
    student = make_class(size=1)["students"][0]
    clock.set_local(2026, 11, 14)

    response = client.post("/api/admin/test-mode", json={"enabled": True}, headers=admin)

    assert response.json() == {"test_mode": True, "phase": "running"}
    assert client.post("/api/days/3/open", headers=kid(student["code"])).status_code == 200


def test_admin_can_turn_test_mode_off(client, admin, make_class):
    student = make_class(size=1)["students"][0]
    client.post("/api/admin/test-mode", json={"enabled": True}, headers=admin)

    client.post("/api/admin/test-mode", json={"enabled": False}, headers=admin)

    assert client.post("/api/days/3/open", headers=kid(student["code"])).status_code == 403
    assert client.get("/api/days/1/reveal", headers=kid(student["code"])).status_code == 404


def test_test_mode_toggle_requires_admin(client):
    response = client.post("/api/admin/test-mode", json={"enabled": True})

    assert response.status_code == 401


def test_unused_task_set_can_be_deleted(client, admin):
    client.post("/api/admin/classes", json={"name": "4a", "task_set": "simple", "size": 1}, headers=admin)
    client.patch("/api/admin/classes/1", json={}, headers=admin)
    client.post("/api/admin/classes", json={"name": "x", "task_set": "simple", "size": 1}, headers=admin)

    response = client.delete("/api/admin/task-sets/nope", headers=admin)

    assert response.status_code == 404


def test_task_set_used_by_class_cannot_be_deleted(client, admin, make_class):
    make_class(name="4a")

    response = client.delete("/api/admin/task-sets/simple", headers=admin)

    assert response.status_code == 409
    assert "4a" in response.json()["detail"]


def test_deleted_task_set_disappears_from_overview(client, admin):
    response = client.delete("/api/admin/task-sets/simple", headers=admin)

    overview = client.get("/api/admin/overview", headers=admin).json()
    assert response.json() == {"deleted": "simple"}
    assert overview["task_sets"] == []
