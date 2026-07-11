"""Tests for the feature-flagged React explorer at /beta/projects."""


def test_spa_hidden_when_flag_off(app, client, make_user, login):
    """Default posture: flag off → 404, exactly like production."""
    make_user("spa@example.com")
    login("spa@example.com")
    app.config["FEATURE_SPA"] = False
    assert client.get("/beta/projects").status_code == 404


def test_spa_requires_login_even_with_flag_on(app, client):
    app.config["FEATURE_SPA"] = True
    try:
        resp = client.get("/beta/projects")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]
    finally:
        app.config["FEATURE_SPA"] = False


def test_spa_serves_when_flag_on(app, client, make_user, login):
    make_user("spa2@example.com")
    login("spa2@example.com")
    app.config["FEATURE_SPA"] = True
    try:
        resp = client.get("/beta/projects")
        assert resp.status_code == 200
        assert 'id="pb-spa-root"' in resp.get_data(as_text=True)
        assert "/static/spa/spa.js" in resp.get_data(as_text=True)
    finally:
        app.config["FEATURE_SPA"] = False
