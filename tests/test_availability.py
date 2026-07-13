"""End-to-end tests for weekly availability, team meeting-time overlap, and the
calendar (.ics) deadline export."""
from datetime import datetime

from extensions import db as _db
from models import User, Project, UserAvailability


def test_save_and_render_availability(app, client, login, make_user):
    make_user("u@t.local")
    login("u@t.local")
    r = client.post("/availability",
                    json={"cells": [[0, 1], [2, 2]], "timezone": "Europe/Sarajevo"})
    assert r.get_json() == {"ok": True, "count": 2}
    with app.app_context():
        assert UserAvailability.query.count() == 2
        assert User.query.filter_by(email="u@t.local").first().timezone == "Europe/Sarajevo"
    assert client.get("/availability").status_code == 200


def test_invalid_availability_cell_rejected(client, login, make_user):
    make_user("u@t.local")
    login("u@t.local")
    r = client.post("/availability", json={"cells": [[9, 9]], "timezone": ""})
    # out-of-range cells are silently dropped, not an error
    assert r.get_json()["count"] == 0


def test_project_detail_shows_meeting_overlap(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local", first="Owner")
    pid = make_project(owner)
    with app.app_context():
        _db.session.add_all([
            UserAvailability(user_id=owner, weekday=0, block=0),
            UserAvailability(user_id=owner, weekday=1, block=2),
        ])
        _db.session.commit()
    login("owner@t.local")
    r = client.get(f"/project/{pid}")
    assert r.status_code == 200
    assert b"Best times to meet" in r.data


def test_project_deadline_ics(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    pid = make_project(owner)
    with app.app_context():
        p = _db.session.get(Project, pid)
        p.deadline = datetime(2026, 12, 1)
        _db.session.commit()
    login("owner@t.local")
    r = client.get(f"/project/{pid}/deadline.ics")
    assert r.status_code == 200
    assert r.mimetype == "text/calendar"
    assert b"BEGIN:VEVENT" in r.data
    assert b"DTSTART;VALUE=DATE:20261201" in r.data


def test_my_calendar_ics(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    pid = make_project(owner)
    with app.app_context():
        p = _db.session.get(Project, pid)
        p.deadline = datetime(2026, 11, 15)
        _db.session.commit()
    login("owner@t.local")
    r = client.get("/calendar.ics")
    assert r.status_code == 200
    assert r.mimetype == "text/calendar"
    assert b"BEGIN:VCALENDAR" in r.data
