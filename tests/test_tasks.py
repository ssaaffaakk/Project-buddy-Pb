"""Tests for the Celery task layer (eager mode — no broker in tests)."""
from datetime import datetime, timedelta

from celery_app import celery, has_broker
from extensions import db
from models import Project


def test_no_broker_means_eager(app):
    assert not has_broker()
    assert celery.conf.task_always_eager is True


def test_deadline_task_completes_overdue_projects(app, make_user):
    owner = make_user("task-owner@example.com")
    with app.app_context():
        p = Project(title="Overdue", description="x", owner_id=owner,
                    team_size=3, status="open",
                    deadline=datetime.utcnow() - timedelta(days=1))
        db.session.add(p)
        db.session.commit()
        pid = p.id

        from services.tasks import check_deadlines_task
        check_deadlines_task.delay()  # eager → runs inline

        assert db.session.get(Project, pid).status == "completed"


def test_send_email_without_key_is_graceful(app, monkeypatch):
    from routes import email as email_mod
    called = []
    monkeypatch.setattr("services.tasks.dispatch_email",
                        lambda *a, **k: called.append(a))
    with app.test_request_context():
        monkeypatch.setitem(app.config, "BREVO_API_KEY", "")
        assert email_mod.send_email("x@example.com", "s", "b") is False
        assert called == []  # nothing dispatched without a key


def test_send_email_dispatches_when_configured(app, monkeypatch):
    from routes import email as email_mod
    called = []
    monkeypatch.setattr("services.tasks.dispatch_email",
                        lambda *a, **k: called.append((a, k)))
    with app.test_request_context():
        monkeypatch.setitem(app.config, "BREVO_API_KEY", "fake-key")
        assert email_mod.send_email("x@example.com", "s", "b", is_html=True) is True
        assert len(called) == 1
        args, kwargs = called[0]
        assert args[0] == "x@example.com"
        assert kwargs.get("is_html") is True
