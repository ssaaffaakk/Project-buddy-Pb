"""Regression tests for real-time group chat (SocketIO broadcast on send).

Locks in the behavior from the polling→SocketIO change: POST .../send must
broadcast an 'sg_message' event to the group's collab room with the message
payload, and only members may send. socketio.emit is captured so nothing
actually goes over the wire.
"""
from extensions import db, socketio
from models import StudyGroup, StudyGroupMember, User


def _group_with_member(app, email):
    """Create a group whose sole member is its creator; return (group_id, user_id)."""
    with app.app_context():
        u = User(first_name="M", last_name="e", email=email, role="student")
        u.set_password("Test1234!")
        db.session.add(u)
        db.session.flush()
        g = StudyGroup(name="G", creator_id=u.id)
        db.session.add(g)
        db.session.flush()
        db.session.add(StudyGroupMember(group_id=g.id, user_id=u.id))
        db.session.commit()
        return g.id, u.id


def test_send_broadcasts_sg_message_to_collab_room(app, client, login, monkeypatch):
    gid, uid = _group_with_member(app, "chat-rt@example.com")
    login("chat-rt@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append((a, k)))

    resp = client.post(f"/study-groups/{gid}/send", json={"body": "hello realtime"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["body"] == "hello realtime"

    # Exactly one sg_message broadcast, to the collab room, with the sent message.
    sg = [(a, k) for (a, k) in calls if a and a[0] == "sg_message"]
    assert len(sg) == 1
    args, kwargs = sg[0]
    assert args[1]["id"] == payload["id"]
    assert args[1]["body"] == "hello realtime"
    assert args[1]["author_id"] == uid
    assert kwargs.get("to") == f"collab_{gid}"


def test_non_member_send_is_rejected_and_emits_nothing(app, client, make_user, login, monkeypatch):
    gid, _ = _group_with_member(app, "chat-owner@example.com")
    make_user("chat-outsider@example.com")
    login("chat-outsider@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append(a))

    resp = client.post(f"/study-groups/{gid}/send", json={"body": "let me in"})
    assert resp.status_code == 403
    assert not any(a and a[0] == "sg_message" for a in calls)


def test_empty_message_is_rejected_and_emits_nothing(app, client, login, monkeypatch):
    gid, _ = _group_with_member(app, "chat-empty@example.com")
    login("chat-empty@example.com")

    calls = []
    monkeypatch.setattr(socketio, "emit", lambda *a, **k: calls.append(a))

    resp = client.post(f"/study-groups/{gid}/send", json={"body": "   "})
    assert resp.status_code == 400
    assert not any(a and a[0] == "sg_message" for a in calls)


# ── Typing indicator (sg_typing SocketIO handler) ────────────────────────────────

def _add_member(app, gid, email):
    with app.app_context():
        u = User(first_name="U", last_name="x", email=email, role="student")
        u.set_password("Test1234!")
        db.session.add(u)
        db.session.flush()
        db.session.add(StudyGroupMember(group_id=gid, user_id=u.id))
        db.session.commit()
        return u.id


def _login_client(app, email):
    c = app.test_client()
    c.post("/auth/login", data={"email": email, "password": "Test1234!"})
    return c


def test_sg_typing_relays_to_other_member_not_self(app):
    gid, _ = _group_with_member(app, "typ-a@example.com")
    _add_member(app, gid, "typ-b@example.com")
    sa = socketio.test_client(app, flask_test_client=_login_client(app, "typ-a@example.com"))
    sb = socketio.test_client(app, flask_test_client=_login_client(app, "typ-b@example.com"))
    sa.get_received()                                  # drain connect
    sb.get_received()
    sa.emit("join_collab", {"group_id": gid})
    sb.emit("join_collab", {"group_id": gid})
    sa.get_received()                                  # drain join
    sb.get_received()

    sa.emit("sg_typing", {"group_id": gid})
    a_events = sa.get_received()
    b_events = sb.get_received()

    assert not any(e["name"] == "sg_typing" for e in a_events)   # include_self=False
    typing = [e for e in b_events if e["name"] == "sg_typing"]
    assert len(typing) == 1 and "name" in typing[0]["args"][0]
    sa.disconnect()
    sb.disconnect()


def test_sg_typing_from_non_member_is_ignored(app):
    gid, _ = _group_with_member(app, "typ-m@example.com")
    with app.app_context():                            # an outsider, not in the group
        o = User(first_name="O", last_name="ut", email="typ-out@example.com", role="student")
        o.set_password("Test1234!")
        db.session.add(o)
        db.session.commit()
    sm = socketio.test_client(app, flask_test_client=_login_client(app, "typ-m@example.com"))
    so = socketio.test_client(app, flask_test_client=_login_client(app, "typ-out@example.com"))
    sm.get_received()
    so.get_received()
    sm.emit("join_collab", {"group_id": gid})
    sm.get_received()

    so.emit("sg_typing", {"group_id": gid})            # outsider can't broadcast in
    assert not any(e["name"] == "sg_typing" for e in sm.get_received())
    sm.disconnect()
    so.disconnect()
