"""Smoke tests for ProjectBuddy's critical flows.

These are deliberately high-level: they exercise auth, the application flow,
role-based authorization, and the study-group voice gate end-to-end so that a
regression in any of them fails loudly instead of silently.
"""
from extensions import db
from models import Application, PushSubscription, StudyGroup, StudyGroupMember

# ── Auth ──────────────────────────────────────────────────────────────────────

def test_protected_page_redirects_when_anonymous(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_valid_credentials(client, make_user, login):
    make_user("alice@example.com")
    resp = login("alice@example.com")
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]
    # session is now authenticated → protected page renders
    assert client.get("/dashboard").status_code == 200


def test_login_invalid_password_rejected(client, make_user, login):
    make_user("bob@example.com")
    resp = login("bob@example.com", password="wrong-password")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    # still anonymous → dashboard bounces back to login
    assert "/auth/login" in client.get("/dashboard").headers.get("Location", "")


# ── Application flow ────────────────────────────────────────────────────────────

def test_applicant_can_apply_to_project(app, client, make_user, make_project, login):
    owner = make_user("owner@example.com")
    applicant = make_user("applicant@example.com")
    pid = make_project(owner)

    login("applicant@example.com")
    resp = client.post(f"/projects/{pid}/apply", data={}, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        appn = Application.query.filter_by(project_id=pid, applicant_id=applicant).first()
        assert appn is not None
        assert appn.status == "pending"


def test_owner_cannot_apply_to_own_project(app, client, make_user, make_project, login):
    owner = make_user("owner2@example.com")
    pid = make_project(owner)

    login("owner2@example.com")
    client.post(f"/projects/{pid}/apply", data={}, follow_redirects=False)

    with app.app_context():
        assert Application.query.filter_by(project_id=pid, applicant_id=owner).count() == 0


# ── Role-based authorization ────────────────────────────────────────────────────

def test_non_admin_cannot_reach_admin_endpoint(client, make_user, login):
    make_user("student@example.com", role="student")
    login("student@example.com")
    resp = client.get("/admin/reports")
    # admin_required redirects non-admins away rather than serving the JSON
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_admin_can_reach_admin_endpoint(client, make_user, login):
    make_user("admin@example.com", role="admin")
    login("admin@example.com")
    resp = client.get("/admin/reports")
    assert resp.status_code == 200
    assert "reports" in resp.get_json()


# ── Voice-chat membership gate (locks in the SocketIO authz fix) ────────────────

def _make_group_with_member(app, member_id=None):
    with app.app_context():
        g = StudyGroup(name="Secure Group", topic="Security", creator_id=member_id or 1)
        db.session.add(g)
        db.session.flush()
        if member_id is not None:
            db.session.add(StudyGroupMember(group_id=g.id, user_id=member_id))
        db.session.commit()
        return g.id


def _login_client(app, email, password="Test1234!"):
    """A fresh client logged in as `email` (fresh so the login route doesn't
    short-circuit on an already-authenticated session)."""
    c = app.test_client()
    c.post("/auth/login", data={"email": email, "password": password})
    return c


def _join_voice_events(app, client, socketio, gid):
    """Emit join_voice over a SocketIO client bound to `client`'s session and
    return the set of event names received in response."""
    sio = socketio.test_client(app, flask_test_client=client)
    sio.get_received()  # drain connect events
    sio.emit("join_voice", {"group_id": gid})
    events = {e["name"] for e in sio.get_received()}
    sio.disconnect()
    return events


def test_push_subscribe_requires_login(client):
    resp = client.post("/push/subscribe", json={})
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_push_subscribe_stores_subscription(app, client, make_user, login):
    uid = make_user("pushuser@example.com")
    login("pushuser@example.com")
    sub = {
        "endpoint": "https://push.example.com/abc123",
        "keys": {"p256dh": "BExamplePublicKey", "auth": "authsecret"},
    }
    resp = client.post("/push/subscribe", json=sub)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        row = PushSubscription.query.filter_by(user_id=uid).first()
        assert row is not None
        assert row.endpoint == sub["endpoint"]

    # unsubscribe removes it
    assert client.post("/push/unsubscribe", json={"endpoint": sub["endpoint"]}).status_code == 200
    with app.app_context():
        assert PushSubscription.query.filter_by(user_id=uid).count() == 0


def test_push_subscribe_rejects_incomplete_payload(client, make_user, login):
    make_user("pushuser2@example.com")
    login("pushuser2@example.com")
    resp = client.post("/push/subscribe", json={"endpoint": "https://x/y"})  # no keys
    assert resp.status_code == 400


def test_voice_membership_gate(app, make_user, socketio):
    """Non-members are rejected from a group's voice call; members are admitted.

    Uses one app instance (SocketIO is a global singleton) and a separate logged-in
    client per identity.
    """
    member = make_user("member@example.com")
    make_user("outsider@example.com")
    gid = _make_group_with_member(app, member_id=member)

    # Outsider: rejected with an error, never sees the participant roster.
    outsider_events = _join_voice_events(
        app, _login_client(app, "outsider@example.com"), socketio, gid)
    assert "voice_error" in outsider_events
    assert "voice_existing_participants" not in outsider_events

    # Member: admitted, receives the participant roster.
    member_events = _join_voice_events(
        app, _login_client(app, "member@example.com"), socketio, gid)
    assert "voice_existing_participants" in member_events
    assert "voice_error" not in member_events
