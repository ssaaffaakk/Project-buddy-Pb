"""Real-time project chat: POST /project/<id>/message saves the message and
broadcasts 'project_message' to the project's room, and only the team (plus
admins) can join that room.
"""
from extensions import db, socketio
from models import ProjectMember


def _add_member(app, project_id, user_id):
    with app.app_context():
        db.session.add(ProjectMember(project_id=project_id, user_id=user_id))
        db.session.commit()


def _login_client(app, email):
    c = app.test_client()
    c.post("/auth/login", data={"email": email, "password": "Test1234!"})
    return c


def test_send_broadcasts_to_the_project_room(app, client, make_user, make_project, login, monkeypatch):
    owner = make_user("pc-owner@example.com")
    pid = make_project(owner)
    login("pc-owner@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append((a, k)))

    resp = client.post(f"/project/{pid}/message", json={"content": "standup at 10?"})
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["content"] == "standup at 10?"
    assert payload["sender_id"] == owner

    sent = [(a, k) for (a, k) in calls if a and a[0] == "project_message"]
    assert len(sent) == 1
    args, kwargs = sent[0]
    assert args[1]["id"] == payload["id"]
    assert kwargs.get("to") == f"project_{pid}"


def test_outsider_send_is_rejected_and_emits_nothing(app, client, make_user, make_project, login, monkeypatch):
    pid = make_project(make_user("pc-owner2@example.com"))
    make_user("pc-outsider@example.com")
    login("pc-outsider@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append(a))

    resp = client.post(f"/project/{pid}/message", json={"content": "hi team"})
    assert resp.status_code == 403
    assert not any(a and a[0] == "project_message" for a in calls)


def test_team_receives_live_messages_and_outsiders_do_not(app, make_user, make_project):
    owner = make_user("pc-live-owner@example.com")
    member = make_user("pc-live-member@example.com")
    make_user("pc-live-outsider@example.com")
    pid = make_project(owner)
    _add_member(app, pid, member)

    owner_http = _login_client(app, "pc-live-owner@example.com")
    sm = socketio.test_client(app, flask_test_client=_login_client(app, "pc-live-member@example.com"))
    so = socketio.test_client(app, flask_test_client=_login_client(app, "pc-live-outsider@example.com"))
    sm.emit("join_project", {"project_id": pid})
    so.emit("join_project", {"project_id": pid})       # not on the team: ignored
    sm.get_received()
    so.get_received()

    resp = owner_http.post(f"/project/{pid}/message", json={"content": "pushed live"})
    assert resp.status_code == 201

    live = [e for e in sm.get_received() if e["name"] == "project_message"]
    assert len(live) == 1 and live[0]["args"][0]["content"] == "pushed live"
    assert not any(e["name"] == "project_message" for e in so.get_received())
    sm.disconnect()
    so.disconnect()
