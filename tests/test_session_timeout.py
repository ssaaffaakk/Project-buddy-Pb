"""Tests for the idle-session timeout (auto sign-out after inactivity).

The before_request hook stores a last-activity timestamp in the session;
background pollers are exempt from refreshing it, so an AFK user with an
open tab still times out. Tests manipulate the timestamp directly via
session_transaction instead of sleeping.
"""
import time


def test_active_user_stays_logged_in(app, client, make_user, login):
    make_user("idle-ok@example.com")
    login("idle-ok@example.com")
    # 10 minutes idle < 30-minute default — still signed in.
    with client.session_transaction() as s:
        s["_last_active"] = time.time() - 10 * 60
    assert client.get("/dashboard").status_code == 200


def test_idle_user_is_signed_out(app, client, make_user, login):
    make_user("idle-out@example.com")
    login("idle-out@example.com")
    assert client.get("/dashboard").status_code == 200
    with client.session_transaction() as s:
        s["_last_active"] = time.time() - 31 * 60
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    # And the session really is gone — the next request is anonymous too.
    assert client.get("/dashboard").status_code == 302


def test_background_poll_checks_but_does_not_extend(app, client, make_user, login):
    make_user("idle-poll@example.com")
    login("idle-poll@example.com")
    stamp = time.time() - 10 * 60
    with client.session_transaction() as s:
        s["_last_active"] = stamp

    # The notifications poll must not reset the idle clock…
    assert client.get("/notifications/unread").status_code == 200
    with client.session_transaction() as s:
        assert s["_last_active"] == stamp

    # …but a real navigation does.
    assert client.get("/dashboard").status_code == 200
    with client.session_transaction() as s:
        assert s["_last_active"] > stamp


def test_expired_session_on_background_poll_also_logs_out(app, client, make_user, login):
    """An AFK tab's own poller is what eventually flips the session out."""
    make_user("idle-bg@example.com")
    login("idle-bg@example.com")
    with client.session_transaction() as s:
        s["_last_active"] = time.time() - 31 * 60
    resp = client.get("/notifications/unread")
    assert resp.status_code == 302  # logged out -> login redirect


def test_timeout_disabled_when_zero(app, client, make_user, login, monkeypatch):
    monkeypatch.setitem(app.config, "SESSION_IDLE_TIMEOUT_MIN", 0)
    make_user("idle-off@example.com")
    login("idle-off@example.com")
    with client.session_transaction() as s:
        s["_last_active"] = time.time() - 24 * 3600
    assert client.get("/dashboard").status_code == 200
