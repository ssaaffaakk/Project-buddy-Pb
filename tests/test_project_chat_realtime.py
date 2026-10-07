"""Regression tests for project chat: live SocketIO delivery, member-gated
room joins, coalesced notifications, and JSON (not flash+redirect) errors for
fetch callers so a failed send can't look like a success.
"""
import logging

from extensions import db, socketio
from models import Notification, ProjectMember


def _add_member(app, project_id, user_id, removed=False):
    with app.app_context():
        db.session.add(ProjectMember(project_id=project_id, user_id=user_id, removed=removed))
        db.session.commit()


def _login_client(app, email):
    c = app.test_client()
    c.post("/auth/login", data={"email": email, "password": "Test1234!"})
    return c


def _chat_notifs(app, user_id):
    with app.app_context():
        return Notification.query.filter_by(user_id=user_id, type="project_chat").all()


def test_send_broadcasts_to_project_room(app, client, make_user, make_project, login, monkeypatch):
    owner = make_user("pc-owner@example.com")
    pid = make_project(owner)
    login("pc-owner@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append((a, k)))

    resp = client.post(f"/project/{pid}/message", json={"content": "hello team"})
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["content"] == "hello team" and payload["sender_id"] == owner

    pm = [(a, k) for (a, k) in calls if a and a[0] == "project_message"]
    assert len(pm) == 1
    args, kwargs = pm[0]
    assert args[1]["id"] == payload["id"]
    assert kwargs.get("to") == f"project_{pid}"


def test_non_member_send_is_rejected_and_emits_nothing(app, client, make_user, make_project, login,
                                                       monkeypatch):
    pid = make_project(make_user("pc-own2@example.com"))
    make_user("pc-out@example.com")
    login("pc-out@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append(a))

    resp = client.post(f"/project/{pid}/message", json={"content": "let me in"})
    assert resp.status_code == 403
    assert not any(a and a[0] == "project_message" for a in calls)


def test_send_notifies_other_participants_coalesced(app, make_user, make_project, monkeypatch):
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: None)
    owner = make_user("pc-n-owner@example.com")
    member = make_user("pc-n-member@example.com")
    gone = make_user("pc-n-gone@example.com")
    pid = make_project(owner)
    _add_member(app, pid, member)
    _add_member(app, pid, gone, removed=True)

    oc = _login_client(app, "pc-n-owner@example.com")
    oc.post(f"/project/{pid}/message", json={"content": "one"})
    oc.post(f"/project/{pid}/message", json={"content": "two"})

    # One unread notice for the active member, none for the sender or a removed member.
    assert len(_chat_notifs(app, member)) == 1
    assert _chat_notifs(app, owner) == []
    assert _chat_notifs(app, gone) == []

    # Opening the project page reads it; the next message notifies again.
    mc = _login_client(app, "pc-n-member@example.com")
    assert mc.get(f"/project/{pid}").status_code == 200
    assert all(n.is_read for n in _chat_notifs(app, member))
    oc.post(f"/project/{pid}/message", json={"content": "three"})
    assert len(_chat_notifs(app, member)) == 2


def test_member_receives_live_message_outsider_cannot_join(app, make_user, make_project):
    owner = make_user("pc-l-owner@example.com")
    member = make_user("pc-l-member@example.com")
    make_user("pc-l-out@example.com")
    pid = make_project(owner)
    _add_member(app, pid, member)

    oc = _login_client(app, "pc-l-owner@example.com")
    sm = socketio.test_client(app, flask_test_client=_login_client(app, "pc-l-member@example.com"))
    so = socketio.test_client(app, flask_test_client=_login_client(app, "pc-l-out@example.com"))
    sm.get_received()
    so.get_received()

    assert sm.emit("join_project", {"project_id": pid}, callback=True) is True
    assert so.emit("join_project", {"project_id": pid}, callback=True) is False

    oc.post(f"/project/{pid}/message", json={"content": "live!"})
    live = [e for e in sm.get_received() if e["name"] == "project_message"]
    assert len(live) == 1 and live[0]["args"][0]["content"] == "live!"
    assert not any(e["name"] == "project_message" for e in so.get_received())
    sm.disconnect()
    so.disconnect()


def test_csrf_failure_is_json_for_fetch_and_redirect_for_forms(app, client, make_user, make_project,
                                                               login, monkeypatch):
    pid = make_project(make_user("pc-csrf@example.com"))
    login("pc-csrf@example.com")
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)

    # fetch(): previously a followed redirect → 200 HTML → treated as sent.
    resp = client.post(f"/project/{pid}/message", json={"content": "x"},
                       headers={"Sec-Fetch-Mode": "cors"})
    assert resp.status_code == 400
    assert "Session expired" in resp.get_json()["error"]

    # A plain form navigation keeps the flash + redirect.
    resp = client.post(f"/project/{pid}/message", data={"content": "x"},
                       headers={"Sec-Fetch-Mode": "navigate"})
    assert resp.status_code == 302


def test_socket_handler_errors_are_logged_with_event_name(app, caplog):
    @socketio.on("_test_boom")
    def _boom(data):
        raise RuntimeError("boom")

    sc = socketio.test_client(app)
    with caplog.at_level(logging.ERROR):
        sc.emit("_test_boom", {})
    assert any("'_test_boom' failed" in r.getMessage() for r in caplog.records)
    sc.disconnect()
