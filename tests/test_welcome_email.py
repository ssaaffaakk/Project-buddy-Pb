from unittest.mock import patch
from models import User


def test_register_sends_welcome_email(client, app):
    with patch("routes.email.send_email", return_value=True) as m:
        r = client.post("/auth/register", data={
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com", "department": "CS",
            "password": "Passw0rd!", "password_confirm": "Passw0rd!",
            "interest_tags": ["python", "ai / ml", "backend", "data", "web"],
        }, follow_redirects=False)
    assert r.status_code in (302, 303), r.data[:400]
    with app.app_context():
        assert User.query.filter_by(email="ada@example.com").first() is not None
    assert m.called, "welcome email was not dispatched"
    assert "Welcome to ProjectBuddy" in m.call_args[0][1]


def test_signup_survives_dead_mail_provider(client, app):
    """A broken mail provider must not block the signup."""
    with patch("routes.email.send_email", side_effect=RuntimeError("brevo down")):
        r = client.post("/auth/register", data={
            "first_name": "Grace", "last_name": "Hopper",
            "email": "grace@example.com", "department": "CS",
            "password": "Passw0rd!", "password_confirm": "Passw0rd!",
            "interest_tags": ["python", "ai / ml", "backend", "data", "web"],
        }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        assert User.query.filter_by(email="grace@example.com").first() is not None


def test_welcome_email_reaches_brevo(client, app):
    """End-to-end: only the Brevo HTTP boundary is faked, so the whole chain
    (route → send_welcome_email → send_email → dispatch → deliver_email) is
    exercised for real. Guards against the email being wired up but never
    actually leaving the process."""
    import time
    from unittest.mock import MagicMock

    app.config["BREVO_API_KEY"] = "test-key-not-real"
    app.config["MAIL_DEFAULT_SENDER"] = "noreply@projectbuddy.test"
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        r = MagicMock()
        r.status_code = 201
        return r

    with patch("requests.post", side_effect=fake_post):
        r = client.post("/auth/register", data={
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com", "department": "CS",
            "password": "Passw0rd!", "password_confirm": "Passw0rd!",
            "interest_tags": ["python", "ai / ml", "backend", "data", "web"],
        }, follow_redirects=False)
        assert r.status_code in (302, 303)

        # Delivery runs on a background thread — wait for it.
        for _ in range(50):
            if calls:
                break
            time.sleep(0.1)

    assert calls, "Brevo was never called — the welcome email did not go out"
    url, kw = calls[0]
    payload = kw["json"]
    assert "api.brevo.com" in url
    assert payload["to"] == [{"email": "ada@example.com"}]
    assert payload["subject"] == "Welcome to ProjectBuddy"
    assert "Welcome to ProjectBuddy, Ada!" in payload["htmlContent"]
