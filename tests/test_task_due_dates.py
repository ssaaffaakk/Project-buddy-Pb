"""End-to-end tests for kanban task due dates + overdue flagging."""
from datetime import datetime, timezone, timedelta


def test_create_task_with_due_and_overdue_flag(client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    pid = make_project(owner)
    login("owner@t.local")
    past = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    r = client.post(f"/project/{pid}/tasks", json={"title": "late task", "due_date": past})
    assert r.status_code == 201
    task = r.get_json()["task"]
    assert task["due_date"] == past
    assert task["overdue"] is True


def test_set_and_clear_task_due(client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    pid = make_project(owner)
    login("owner@t.local")
    tid = client.post(f"/project/{pid}/tasks", json={"title": "t"}).get_json()["task"]["id"]
    future = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")
    r = client.post(f"/project/{pid}/tasks/{tid}/due", json={"due_date": future})
    assert r.get_json()["task"]["due_date"] == future
    assert r.get_json()["task"]["overdue"] is False
    r2 = client.post(f"/project/{pid}/tasks/{tid}/due", json={"due_date": None})
    assert r2.get_json()["task"]["due_date"] is None


def test_bad_due_date_rejected(client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    pid = make_project(owner)
    login("owner@t.local")
    r = client.post(f"/project/{pid}/tasks", json={"title": "t", "due_date": "not-a-date"})
    assert r.status_code == 400
