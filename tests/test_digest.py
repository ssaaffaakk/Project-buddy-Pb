"""Tests for the weekly recommendation digest (services/digest.py)."""
from datetime import datetime, timedelta

from extensions import db
from models import Notification, Project, ProjectTag, User, UserInterest
from services.digest import send_weekly_digest


def _seed_user_with_match(app):
    """A student with an interest and one open project that matches it."""
    with app.app_context():
        owner = User(first_name="O", last_name="wner", email="digest-owner@x.com",
                     role="student")
        owner.set_password("Test1234!")
        student = User(first_name="S", last_name="tudent", email="digest-student@x.com",
                       role="student")
        student.set_password("Test1234!")
        db.session.add_all([owner, student])
        db.session.flush()
        db.session.add(UserInterest(user_id=student.id, tag="python"))
        p = Project(title="Backend API", description="x", owner_id=owner.id,
                    team_size=4, status="open")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectTag(project_id=p.id, tag="backend"))
        db.session.commit()
        return student.id


def test_digest_creates_notification(app):
    student_id = _seed_user_with_match(app)
    with app.app_context():
        summary = send_weekly_digest()
        assert summary["sent"] >= 1
        notif = Notification.query.filter_by(user_id=student_id, type="digest").first()
        assert notif is not None
        assert "fit" in notif.message
        assert notif.link.startswith("/project/")


def test_digest_is_deduped_within_window(app):
    _seed_user_with_match(app)
    with app.app_context():
        first = send_weekly_digest()
        second = send_weekly_digest()  # immediate re-run
        assert first["sent"] >= 1
        assert second["sent"] == 0     # everyone already notified
        # exactly one digest notification per user
        assert Notification.query.filter_by(type="digest").count() == first["sent"]


def test_digest_redelivers_after_window(app):
    student_id = _seed_user_with_match(app)
    with app.app_context():
        send_weekly_digest()
        # age the existing digest notification past the dedupe window
        n = Notification.query.filter_by(user_id=student_id, type="digest").first()
        n.created_at = datetime.utcnow() - timedelta(days=8)
        db.session.commit()
        again = send_weekly_digest()
        assert again["sent"] >= 1


def test_digest_skips_users_without_recommendations(app):
    with app.app_context():
        u = User(first_name="N", last_name="oInterests", email="nomatch@x.com",
                 role="student")
        u.set_password("Test1234!")
        db.session.add(u)
        db.session.commit()
        summary = send_weekly_digest()
        assert Notification.query.filter_by(user_id=u.id, type="digest").count() == 0
        assert summary["sent"] == 0
