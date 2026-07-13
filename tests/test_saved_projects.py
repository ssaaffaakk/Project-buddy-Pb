"""End-to-end tests for saved projects (bookmarks / watchlist).

Exercised through the real WSGI stack (routes + Jinja templates) so a template
error surfaces as a failing test, not a 500 in production.
"""
from models import SavedProject


def test_toggle_saved_project(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    make_user("viewer@t.local")
    pid = make_project(owner)
    login("viewer@t.local")
    r1 = client.post(f"/projects/{pid}/save")
    assert r1.get_json()["saved"] is True
    r2 = client.post(f"/projects/{pid}/save")
    assert r2.get_json()["saved"] is False
    with app.app_context():
        assert SavedProject.query.count() == 0


def test_saved_page_lists_bookmarks(client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    make_user("viewer@t.local")
    pid = make_project(owner, title="Bookmarked Build")
    login("viewer@t.local")
    client.post(f"/projects/{pid}/save")
    r = client.get("/saved")
    assert r.status_code == 200
    assert b"Bookmarked Build" in r.data


def test_saved_page_empty_state(client, login, make_user):
    make_user("solo@t.local")
    login("solo@t.local")
    assert client.get("/saved").status_code == 200
