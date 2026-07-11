"""Tests for the instructor dashboard (services/instructor_view.py + route)."""
from datetime import datetime, timedelta

from extensions import db
from models import Project, ProjectMessage
from services.instructor_view import course_overview


def _project(app, owner_id, *, title, course=None, deadline=None,
             created_days_ago=0, status="open"):
    with app.app_context():
        p = Project(title=title, description="x", owner_id=owner_id, team_size=4,
                    status=status, course=course, deadline=deadline)
        p.created_at = datetime.utcnow() - timedelta(days=created_days_ago)
        db.session.add(p)
        db.session.commit()
        return p.id


def test_stalled_project_flagged(app, make_user):
    owner = make_user("ins-owner@x.com")
    _project(app, owner, title="Stale One", course="CS101", created_days_ago=20)
    with app.app_context():
        overview = course_overview()
        proj = overview[0]["projects"][0]
        assert proj["level"] in ("watch", "risk")
        assert any("no activity" in f for f in proj["flags"])


def test_overdue_project_is_risk(app, make_user):
    owner = make_user("ins-owner2@x.com")
    _project(app, owner, title="Overdue One", course="CS202",
             deadline=datetime.utcnow() - timedelta(days=3), created_days_ago=20)
    with app.app_context():
        overview = course_overview()
        proj = overview[0]["projects"][0]
        assert proj["level"] == "risk"
        assert any("overdue" in f for f in proj["flags"])


def test_healthy_project_ok(app, make_user):
    owner = make_user("ins-owner3@x.com")
    pid = _project(app, owner, title="Fresh One", course="CS303", created_days_ago=1)
    with app.app_context():
        # a recent message keeps it active
        db.session.add(ProjectMessage(project_id=pid, sender_id=owner, content="hi"))
        db.session.commit()
        proj = course_overview()[0]["projects"][0]
        assert proj["level"] == "ok"
        assert proj["flags"] == []


def test_grouped_and_sorted_by_risk(app, make_user):
    owner = make_user("ins-owner4@x.com")
    _project(app, owner, title="Healthy", course="Safe Course", created_days_ago=0)
    _project(app, owner, title="Overdue", course="Risky Course",
             deadline=datetime.utcnow() - timedelta(days=2), created_days_ago=20)
    with app.app_context():
        overview = course_overview()
        # the course with a risk project sorts first
        assert overview[0]["course"] == "Risky Course"
        assert overview[0]["risk_count"] == 1


def test_route_blocks_students(app, client, make_user, login):
    make_user("student-ins@example.com", role="student")
    login("student-ins@example.com")
    resp = client.get("/instructor")
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_route_allows_instructor(app, client, make_user, login):
    make_user("prof@example.com", role="instructor")
    login("prof@example.com")
    resp = client.get("/instructor")
    assert resp.status_code == 200
    assert "Team health" in resp.get_data(as_text=True)
