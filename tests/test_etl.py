"""Tests for the ELT pipeline (services/etl.py): correctness of the star
schema, idempotency of re-runs, and the data-quality gate."""
import pytest

from extensions import db
from models import (
    DwDailyMetrics,
    DwDimProject,
    DwDimUser,
    DwFactDailyActivity,
    User,
)
from services import analytics
from services.etl import DataQualityError, _quality_checks, _today, freshness, run_pipeline


@pytest.fixture
def seeded(app, make_user, make_project):
    """Two users, one project, a day's worth of events."""
    owner = make_user("etl-owner@example.com")
    member = make_user("etl-user@example.com")
    pid = make_project(owner)
    with app.app_context():
        analytics.track("login", member)
        analytics.track("project_view", member, "project", pid)
        analytics.track("rec_impression", member, "project", pid, variant="ml")
        analytics.track("rec_impression", member, "project", pid, variant="ml")
        analytics.track("rec_click", member, "project", pid, variant="ml")
        analytics.track("login", owner)
        db.session.commit()
    return {"owner": owner, "member": member, "pid": pid}


def test_pipeline_builds_star_schema(app, seeded):
    with app.app_context():
        summary = run_pipeline()

        assert summary["dim_user"] == User.query.count() == DwDimUser.query.count()
        assert DwDimProject.query.count() == 1

        member_fact = DwFactDailyActivity.query.filter_by(
            user_id=seeded["member"], date=_today()).one()
        assert member_fact.logins == 1
        assert member_fact.project_views == 1
        assert member_fact.rec_impressions == 2
        assert member_fact.rec_clicks == 1
        assert member_fact.events_total == 5

        today = DwDailyMetrics.query.filter_by(date=_today()).one()
        assert today.dau == 2                      # owner + member both active
        assert today.signups == 2
        assert today.rec_ctr == 50.0               # 1 click / 2 impressions


def test_pipeline_is_idempotent(app, seeded):
    with app.app_context():
        first = run_pipeline()
        second = run_pipeline()
        assert first["dim_user"] == second["dim_user"]
        assert first["fact_daily_activity"] == second["fact_daily_activity"]
        # re-run must not duplicate rows
        assert DwFactDailyActivity.query.count() == second["fact_daily_activity"]
        assert DwDailyMetrics.query.filter_by(date=_today()).count() == 1


def test_quality_gate_catches_missing_rows(app, seeded):
    with app.app_context():
        run_pipeline()
        # sabotage: drop a dimension row → parity check must fail loudly
        DwDimUser.query.filter_by(user_id=seeded["member"]).delete()
        db.session.flush()
        with pytest.raises(DataQualityError):
            _quality_checks(_today())


def test_freshness_never_raises(app):
    with app.app_context():
        info = freshness()
        assert info is not None
        assert "dim_user_rows" in info


def test_admin_analytics_shows_warehouse_card(app, client, make_user, login):
    make_user("etl-admin@example.com", role="admin")
    with app.app_context():
        run_pipeline()
    login("etl-admin@example.com")
    html = client.get("/admin/analytics").get_data(as_text=True)
    assert "Data Warehouse" in html
