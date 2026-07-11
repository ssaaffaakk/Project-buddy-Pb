"""Tests for the project kanban board (routes + ProjectTask model).

Authorization is the critical surface: only project members/owner may read or
mutate tasks; only the creator or owner may delete.
"""
from extensions import db
from models import Project, ProjectMember, ProjectTask, User


def _project_with_member(app, owner_email, member_email):
    with app.app_context():
        owner = User(first_name="O", last_name="w", email=owner_email, role="student")
        owner.set_password("Test1234!")
        member = User(first_name="M", last_name="e", email=member_email, role="student")
        member.set_password("Test1234!")
        db.session.add_all([owner, member])
        db.session.flush()
        p = Project(title="Board P", description="x", owner_id=owner.id,
                    team_size=4, status="open")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(project_id=p.id, user_id=member.id))
        db.session.commit()
        return p.id, owner.id, member.id


def test_member_can_create_and_list(app, client, login):
    pid, _owner, _member = _project_with_member(app, "bo@x.com", "bm@x.com")
    login("bm@x.com")
    r = client.post(f"/project/{pid}/tasks", json={"title": "Write README"})
    assert r.status_code == 201
    assert r.get_json()["task"]["title"] == "Write README"

    tasks = client.get(f"/project/{pid}/tasks").get_json()["tasks"]
    assert len(tasks) == 1 and tasks[0]["status"] == "todo"


def test_non_member_is_blocked_everywhere(app, client, make_user, login):
    pid, _owner, _member = _project_with_member(app, "bo2@x.com", "bm2@x.com")
    make_user("outsider@example.com")
    login("outsider@example.com")
    assert client.get(f"/project/{pid}/tasks").status_code == 403
    assert client.post(f"/project/{pid}/tasks", json={"title": "x"}).status_code == 403


def test_move_task_between_columns(app, client, login):
    pid, _owner, member = _project_with_member(app, "bo3@x.com", "bm3@x.com")
    login("bm3@x.com")
    tid = client.post(f"/project/{pid}/tasks", json={"title": "T"}).get_json()["task"]["id"]

    r = client.post(f"/project/{pid}/tasks/{tid}/move", json={"status": "doing"})
    assert r.status_code == 200 and r.get_json()["task"]["status"] == "doing"

    bad = client.post(f"/project/{pid}/tasks/{tid}/move", json={"status": "nope"})
    assert bad.status_code == 400


def test_assign_must_be_member(app, client, make_user, login):
    pid, owner, member = _project_with_member(app, "bo4@x.com", "bm4@x.com")
    stranger = make_user("stranger@example.com")
    login("bm4@x.com")
    tid = client.post(f"/project/{pid}/tasks", json={"title": "T"}).get_json()["task"]["id"]

    ok = client.post(f"/project/{pid}/tasks/{tid}/assign", json={"user_id": owner})
    assert ok.status_code == 200 and ok.get_json()["task"]["assignee_id"] == owner

    bad = client.post(f"/project/{pid}/tasks/{tid}/assign", json={"user_id": stranger})
    assert bad.status_code == 400  # not a project member

    cleared = client.post(f"/project/{pid}/tasks/{tid}/assign", json={"user_id": None})
    assert cleared.get_json()["task"]["assignee_id"] is None


def test_only_creator_or_owner_deletes(app, client, login):
    pid, _owner, _member = _project_with_member(app, "bo5@x.com", "bm5@x.com")
    # member creates a task
    login("bm5@x.com")
    tid = client.post(f"/project/{pid}/tasks", json={"title": "T"}).get_json()["task"]["id"]

    # owner (different user) can delete a member's task — log out first so the
    # login route (which ignores re-login while authenticated) actually switches
    client.get("/auth/logout")
    login("bo5@x.com")
    assert client.post(f"/project/{pid}/tasks/{tid}/delete").status_code == 200
    with app.app_context():
        assert db.session.get(ProjectTask, tid) is None


def test_delete_forbidden_for_other_member(app, client, make_user, login):
    pid, _owner, _member = _project_with_member(app, "bo6@x.com", "bm6@x.com")
    # a second member joins
    with app.app_context():
        other = User(first_name="X", last_name="y", email="bm6b@x.com", role="student")
        other.set_password("Test1234!")
        db.session.add(other)
        db.session.flush()
        db.session.add(ProjectMember(project_id=pid, user_id=other.id))
        db.session.commit()

    login("bm6@x.com")
    tid = client.post(f"/project/{pid}/tasks", json={"title": "T"}).get_json()["task"]["id"]
    # the other member (not creator, not owner) cannot delete it
    client.get("/auth/logout")
    login("bm6b@x.com")
    assert client.post(f"/project/{pid}/tasks/{tid}/delete").status_code == 403
