"""End-to-end tests for withdrawing a pending project application."""
from extensions import db as _db
from models import Application


def test_withdraw_pending_application(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    applicant = make_user("applicant@t.local")
    pid = make_project(owner)
    with app.app_context():
        _db.session.add(Application(project_id=pid, applicant_id=applicant, status="pending"))
        _db.session.commit()
    login("applicant@t.local")
    r = client.post(f"/projects/{pid}/withdraw", follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        assert Application.query.count() == 0


def test_cannot_withdraw_accepted_application(app, client, login, make_user, make_project):
    owner = make_user("owner@t.local")
    applicant = make_user("applicant@t.local")
    pid = make_project(owner)
    with app.app_context():
        _db.session.add(Application(project_id=pid, applicant_id=applicant, status="accepted"))
        _db.session.commit()
    login("applicant@t.local")
    client.post(f"/projects/{pid}/withdraw", follow_redirects=False)
    with app.app_context():
        assert Application.query.count() == 1  # untouched
