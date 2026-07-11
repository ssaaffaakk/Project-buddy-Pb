"""Tests for the product-analytics event stream (services/analytics.py).

Covers: event writes from real routes, A/B arm assignment determinism,
and the metric aggregations that feed the admin dashboard.
"""
from extensions import db
from models import ActivityEvent
from services import analytics


def _events(app, event):
    with app.app_context():
        return ActivityEvent.query.filter_by(event=event).all()


# ── Event writes from real flows ────────────────────────────────────────────────

def test_login_is_tracked(app, make_user, login):
    uid = make_user("tracked@example.com")
    login("tracked@example.com")
    rows = _events(app, "login")
    assert len(rows) == 1
    assert rows[0].user_id == uid


def test_application_is_tracked(app, client, make_user, make_project, login):
    owner = make_user("owner@example.com")
    applicant = make_user("applicant@example.com")
    pid = make_project(owner)

    login("applicant@example.com")
    client.post(f"/projects/{pid}/apply", data={})

    rows = _events(app, "application_sent")
    assert len(rows) == 1
    assert rows[0].user_id == applicant
    assert rows[0].object_type == "project"
    assert rows[0].object_id == pid


def test_rec_click_attribution(app, client, make_user, make_project, login):
    owner = make_user("owner2@example.com")
    make_user("clicker@example.com")
    pid = make_project(owner)

    login("clicker@example.com")
    # Simulates clicking Apply on a dashboard recommendation card (ml arm)
    client.get(f"/projects/{pid}/apply?src=rec&v=ml")

    rows = _events(app, "rec_click")
    assert len(rows) == 1
    assert rows[0].variant == "ml"
    assert rows[0].object_id == pid


def test_project_view_is_tracked(app, client, make_user, make_project, login):
    owner = make_user("owner3@example.com")
    viewer = make_user("viewer@example.com")
    pid = make_project(owner)

    login("viewer@example.com")
    client.get(f"/project/{pid}")

    rows = _events(app, "project_view")
    assert len(rows) == 1
    assert rows[0].user_id == viewer


def test_track_never_raises(app):
    """A tracking failure must not break the calling request."""
    with app.app_context():
        # event column is String(40) NOT NULL — None would blow up on commit,
        # track() must swallow it.
        analytics.track(None, commit=True)
        assert ActivityEvent.query.count() == 0


# ── A/B assignment ──────────────────────────────────────────────────────────────

def test_ab_variant_deterministic_and_split():
    arms = {analytics.ab_variant(uid) for uid in range(200)}
    assert arms == {"ml", "rules"}  # both arms occur
    for uid in (1, 7, 42):
        assert analytics.ab_variant(uid) == analytics.ab_variant(uid)


# ── Metric aggregations ─────────────────────────────────────────────────────────

def test_funnel_and_active_users(app, client, make_user, make_project, login):
    owner = make_user("f-owner@example.com")
    make_user("f-user@example.com")
    pid = make_project(owner)

    login("f-user@example.com")
    client.post(f"/projects/{pid}/apply", data={})

    with app.app_context():
        funnel = analytics.activation_funnel()
        stages = {s["stage"]: s["count"] for s in funnel}
        assert stages["Signed up"] == 2
        assert stages["Applied to a project"] == 1
        # login + application events → 1 distinct active user
        assert analytics.active_users(days=1) == 1


def test_admin_analytics_page_renders(app, client, make_user, make_project, login):
    """The analytics dashboard renders with funnel/retention/A-B sections."""
    admin = make_user("metrics-admin@example.com", role="admin")
    owner = make_user("metrics-owner@example.com")
    make_project(owner)
    with app.app_context():
        analytics.track("rec_impression", admin, "project", 1, variant="ml", commit=True)

    login("metrics-admin@example.com")
    resp = client.get("/admin/analytics")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Daily Active Users" in html
    assert "Activation Funnel" in html
    assert "Weekly Retention Cohorts" in html


def test_model_card_page_renders(client, make_user, login):
    make_user("mc@example.com")
    login("mc@example.com")
    resp = client.get("/ml/recommender")
    assert resp.status_code == 200


def test_rec_ab_summary_ctr(app, make_user):
    uid = make_user("ab@example.com")
    with app.app_context():
        for _ in range(4):
            analytics.track("rec_impression", uid, "project", 1, variant="ml")
        analytics.track("rec_click", uid, "project", 1, variant="ml")
        analytics.track("rec_impression", uid, "project", 2, variant="rules")
        db.session.commit()

        summary = {row["variant"]: row for row in analytics.rec_ab_summary()}
        assert summary["ml"]["impressions"] == 4
        assert summary["ml"]["clicks"] == 1
        assert summary["ml"]["ctr"] == 25.0
        assert summary["rules"]["clicks"] == 0
