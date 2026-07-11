"""
Product analytics — event tracking and metric queries.

track() writes one ActivityEvent row per user action. It is strictly
best-effort: a tracking failure must never break the request that triggered
it, so every failure is swallowed (and logged).

The metric helpers (active_users, funnel, retention_cohorts, rec_ab_summary)
are SQL-first aggregations consumed by the admin analytics dashboard.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from extensions import db
from models import ActivityEvent, User, Application, Project, ProjectMember

logger = logging.getLogger(__name__)


def _utcnow_naive():
    """DB timestamps are stored naive-UTC (SQLite drops tzinfo) — compare alike."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Writing ───────────────────────────────────────────────────────────────────

def track(event, user_id=None, object_type=None, object_id=None,
          variant=None, value=None, commit=False):
    """Record one analytics event. Never raises.

    commit=False (default) piggybacks on the caller's upcoming
    db.session.commit() so the event lands atomically with the action.
    Use commit=True on read-only paths (page views) that never commit.
    """
    try:
        db.session.add(ActivityEvent(
            user_id=user_id,
            event=event,
            object_type=object_type,
            object_id=object_id,
            variant=variant,
            value=value,
        ))
        if commit:
            db.session.commit()
    except Exception:
        logger.exception("analytics.track(%s) failed", event)
        if commit:
            try:
                db.session.rollback()
            except Exception:
                pass


def commit_quietly():
    """Commit pending tracked events on read-only paths. Never raises."""
    try:
        db.session.commit()
    except Exception:
        logger.exception("analytics commit failed")
        try:
            db.session.rollback()
        except Exception:
            pass


# ── A/B experiment assignment ─────────────────────────────────────────────────

def ab_variant(user_id, experiment="rec_ranker"):
    """Deterministic 50/50 assignment: same user always gets the same arm.

    Hash (not modulo of the raw id) so assignment is independent of signup
    order and stable per experiment name.
    """
    h = hashlib.sha256(f"{experiment}:{user_id}".encode()).digest()
    return "ml" if h[0] % 2 == 0 else "rules"


# ── Reading (admin dashboard metrics) ─────────────────────────────────────────

def active_users(days):
    """Distinct users with any event in the trailing window."""
    since = _utcnow_naive() - timedelta(days=days)
    return (db.session.query(func.count(func.distinct(ActivityEvent.user_id)))
            .filter(ActivityEvent.created_at >= since,
                    ActivityEvent.user_id.isnot(None))
            .scalar() or 0)


def event_count(event, days=None):
    q = db.session.query(func.count(ActivityEvent.id)).filter(ActivityEvent.event == event)
    if days is not None:
        q = q.filter(ActivityEvent.created_at >= _utcnow_naive() - timedelta(days=days))
    return q.scalar() or 0


def activation_funnel():
    """Lifetime activation funnel: signup → onboarded → applied → completed a project.

    Sourced from the core tables (not events) so it covers users who signed
    up before instrumentation existed.
    """
    total = User.query.filter(User.role != "admin").count()
    onboarded = User.query.filter(User.role != "admin", User.onboarded == True).count()  # noqa: E712
    applied = (db.session.query(func.count(func.distinct(Application.applicant_id)))
               .scalar() or 0)
    completed = (db.session.query(func.count(func.distinct(ProjectMember.user_id)))
                 .join(Project, Project.id == ProjectMember.project_id)
                 .filter(Project.status == "completed")
                 .scalar() or 0)
    return [
        {"stage": "Signed up", "count": total},
        {"stage": "Onboarded", "count": onboarded},
        {"stage": "Applied to a project", "count": applied},
        {"stage": "Completed a project", "count": completed},
    ]


def retention_cohorts(weeks=6):
    """Weekly retention: of users who signed up in week W, what % had an
    event in each subsequent week. Returns newest cohort first.

    Computed from ActivityEvent, so history begins when instrumentation
    shipped — early cohorts fill in as data accrues.
    """
    now = _utcnow_naive()
    cohorts = []
    for w in range(weeks):
        start = now - timedelta(weeks=w + 1)
        end = now - timedelta(weeks=w)
        user_ids = [uid for (uid,) in db.session.query(User.id)
                    .filter(User.created_at >= start, User.created_at < end,
                            User.role != "admin").all()]
        row = {"cohort": start.strftime("%b %d"), "size": len(user_ids), "weeks": []}
        for k in range(w + 1):
            k_start = start + timedelta(weeks=k)
            k_end = k_start + timedelta(weeks=1)
            if not user_ids:
                row["weeks"].append(None)
                continue
            active = (db.session.query(func.count(func.distinct(ActivityEvent.user_id)))
                      .filter(ActivityEvent.user_id.in_(user_ids),
                              ActivityEvent.created_at >= k_start,
                              ActivityEvent.created_at < k_end)
                      .scalar() or 0)
            row["weeks"].append(round(active / len(user_ids) * 100))
        cohorts.append(row)
    return cohorts


def rec_ab_summary():
    """Impressions, clicks, and CTR per experiment arm ('ml' vs 'rules')."""
    rows = (db.session.query(
                ActivityEvent.variant,
                ActivityEvent.event,
                func.count(ActivityEvent.id))
            .filter(ActivityEvent.event.in_(["rec_impression", "rec_click"]),
                    ActivityEvent.variant.isnot(None))
            .group_by(ActivityEvent.variant, ActivityEvent.event)
            .all())
    stats = {}
    for variant, event, count in rows:
        stats.setdefault(variant, {"impressions": 0, "clicks": 0})
        key = "impressions" if event == "rec_impression" else "clicks"
        stats[variant][key] = count
    out = []
    for variant in sorted(stats):
        s = stats[variant]
        ctr = round(s["clicks"] / s["impressions"] * 100, 2) if s["impressions"] else 0.0
        out.append({"variant": variant, **s, "ctr": ctr})
    return out
