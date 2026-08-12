"""
ELT pipeline — loads the star-schema warehouse tables (dw_*).

Flow (classic dimensional modeling):
  extract   — application tables + the activity_events stream
  transform — denormalize into user/project dimensions, aggregate the event
              stream into a daily-activity fact table and a daily KPI snapshot
  load      — idempotent: dimensions are fully refreshed, the fact/metrics
              window is delete-then-insert, so re-runs converge to the same state

Every run ends with data-quality checks (row parity, null keys, bounds);
a failed check raises DataQualityError so the scheduler/CLI fails loudly
instead of silently publishing bad numbers.

Run:  flask run-etl          (CLI)
      tasks.run_etl          (nightly Celery beat, 03:00 UTC)

Internal only — nothing user-facing reads these tables; the admin dashboard
shows freshness/row counts.
"""

import logging
import time
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from extensions import db
from models import (
    ActivityEvent,
    Application,
    CommunityPost,
    DwDailyMetrics,
    DwDimProject,
    DwDimUser,
    DwFactDailyActivity,
    Project,
    User,
    UserInterest,
    UserSkill,
)

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30

# fact column ← event name
_FACT_COLUMNS = {
    "logins": "login",
    "project_views": "project_view",
    "applications": "application_sent",
    "rec_impressions": "rec_impression",
    "rec_clicks": "rec_click",
    "chatbot_messages": "chatbot_message",
    "voice_joins": "voice_join",
}


class DataQualityError(RuntimeError):
    """A post-load data-quality check failed — the run must not be trusted."""


def _today():
    return datetime.now(timezone.utc).date()


def _as_date(value):
    """Normalize a grouped-by-date key: func.date() yields 'YYYY-MM-DD' strings
    on SQLite but date objects on PostgreSQL."""
    if isinstance(value, date_type):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date_type.fromisoformat(str(value))


# ── dimensions (full refresh) ─────────────────────────────────────────────────

def _load_dim_user():
    interest_counts = dict(db.session.query(
        UserInterest.user_id, func.count(UserInterest.id)
    ).group_by(UserInterest.user_id).all())
    skill_counts = dict(db.session.query(
        UserSkill.user_id, func.count(UserSkill.id)
    ).group_by(UserSkill.user_id).all())

    from sqlalchemy import or_
    DwDimUser.query.delete()
    for u in User.query.filter(or_(User.is_demo.is_(None), User.is_demo == False)).all():  # noqa: E712
        db.session.add(DwDimUser(
            user_id=u.id,
            full_name=u.get_full_name(),
            role=u.role,
            department=u.department,
            signup_date=u.created_at.date() if u.created_at else None,
            onboarded=u.onboarded,
            is_banned=u.is_banned,
            n_interests=interest_counts.get(u.id, 0),
            n_skills=skill_counts.get(u.id, 0),
        ))
    db.session.flush()
    return User.query.filter(or_(User.is_demo.is_(None), User.is_demo == False)).count()  # noqa: E712


def _load_dim_project():
    DwDimProject.query.delete()
    for p in Project.query.all():
        db.session.add(DwDimProject(
            project_id=p.id,
            title=p.title,
            owner_id=p.owner_id,
            status=p.status,
            course=p.course,
            team_size=p.team_size,
            created_date=p.created_at.date() if p.created_at else None,
            completed_date=p.completed_at.date() if p.completed_at else None,
            n_tags=len(p.topic_tags),
            n_skills=len(p.required_skills),
            n_members=p.current_member_count(),
        ))
    db.session.flush()
    return Project.query.count()


# ── facts (windowed delete-then-insert) ───────────────────────────────────────

def _load_fact_daily_activity(since_date):
    event_date = func.date(ActivityEvent.created_at).label("d")
    rows = (db.session.query(
                event_date,
                ActivityEvent.user_id,
                ActivityEvent.event,
                func.count(ActivityEvent.id))
            .filter(ActivityEvent.user_id.isnot(None),
                    func.date(ActivityEvent.created_at) >= since_date)
            .group_by(event_date, ActivityEvent.user_id, ActivityEvent.event)
            .all())

    # pivot: (date, user) → {event: count}
    pivot = {}
    for d, user_id, event, count in rows:
        pivot.setdefault((_as_date(d), user_id), {})[event] = count

    DwFactDailyActivity.query.filter(DwFactDailyActivity.date >= since_date).delete(
        synchronize_session=False
    )
    for (d, user_id), counts in pivot.items():
        fact = DwFactDailyActivity(
            date=d, user_id=user_id, events_total=sum(counts.values())
        )
        for column, event_name in _FACT_COLUMNS.items():
            setattr(fact, column, counts.get(event_name, 0))
        db.session.add(fact)
    db.session.flush()
    return len(pivot)


def _daily_counts(model, since_date):
    """{date: row_count} for a model's created_at within the window."""
    d = func.date(model.created_at).label("d")
    rows = (db.session.query(d, func.count())
            .filter(func.date(model.created_at) >= since_date)
            .group_by(d).all())
    return {_as_date(day): count for day, count in rows}


def _load_daily_metrics(since_date):
    # DAU + rec counters come from the fact table loaded just before.
    fact_rows = (db.session.query(
                    DwFactDailyActivity.date,
                    func.count(func.distinct(DwFactDailyActivity.user_id)),
                    func.sum(DwFactDailyActivity.rec_impressions),
                    func.sum(DwFactDailyActivity.rec_clicks))
                 .filter(DwFactDailyActivity.date >= since_date)
                 .group_by(DwFactDailyActivity.date)
                 .all())
    by_date = {d: {"dau": dau, "imp": imp or 0, "clk": clk or 0}
               for d, dau, imp, clk in fact_rows}

    signups = _daily_counts(User, since_date)
    applications = _daily_counts(Application, since_date)
    projects = _daily_counts(Project, since_date)
    posts = _daily_counts(CommunityPost, since_date)

    all_dates = (set(by_date) | set(signups) | set(applications)
                 | set(projects) | set(posts))

    DwDailyMetrics.query.filter(DwDailyMetrics.date >= since_date).delete(
        synchronize_session=False
    )
    for d in all_dates:
        f = by_date.get(d, {"dau": 0, "imp": 0, "clk": 0})
        ctr = round(f["clk"] / f["imp"] * 100, 2) if f["imp"] else 0.0
        db.session.add(DwDailyMetrics(
            date=d,
            dau=f["dau"],
            signups=signups.get(d, 0),
            applications=applications.get(d, 0),
            projects_created=projects.get(d, 0),
            posts=posts.get(d, 0),
            rec_impressions=f["imp"],
            rec_clicks=f["clk"],
            rec_ctr=ctr,
        ))
    db.session.flush()
    return len(all_dates)


# ── data quality ──────────────────────────────────────────────────────────────

def _quality_checks(since_date):
    failures = []

    # 1. Row parity: dimensions must mirror the source tables exactly.
    if DwDimUser.query.count() != User.query.count():
        failures.append("dim_user count != users count")
    if DwDimProject.query.count() != Project.query.count():
        failures.append("dim_project count != projects count")

    # 2. Completeness: fact totals must equal the event stream for the window.
    src_total = (db.session.query(func.count(ActivityEvent.id))
                 .filter(ActivityEvent.user_id.isnot(None),
                         func.date(ActivityEvent.created_at) >= since_date)
                 .scalar() or 0)
    fact_total = (db.session.query(func.coalesce(
                      func.sum(DwFactDailyActivity.events_total), 0))
                  .filter(DwFactDailyActivity.date >= since_date)
                  .scalar() or 0)
    if src_total != fact_total:
        failures.append(f"fact events_total {fact_total} != source events {src_total}")

    # 3. Validity: no null keys, CTR within bounds.
    if DwFactDailyActivity.query.filter(DwFactDailyActivity.user_id.is_(None)).count():
        failures.append("fact rows with NULL user_id")
    bad_ctr = DwDailyMetrics.query.filter(
        (DwDailyMetrics.rec_ctr < 0) | (DwDailyMetrics.rec_ctr > 100)
    ).count()
    if bad_ctr:
        failures.append(f"{bad_ctr} daily_metrics rows with CTR outside 0..100")

    if failures:
        raise DataQualityError("; ".join(failures))


# ── entry point ───────────────────────────────────────────────────────────────

def run_pipeline(window_days=DEFAULT_WINDOW_DAYS):
    """Run the full ELT. Returns a run summary dict; raises on quality failure."""
    started = time.monotonic()
    since_date = _today() - timedelta(days=window_days)

    try:
        n_users = _load_dim_user()
        n_projects = _load_dim_project()
        n_fact = _load_fact_daily_activity(since_date)
        n_days = _load_daily_metrics(since_date)
        _quality_checks(since_date)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    summary = {
        "dim_user": n_users,
        "dim_project": n_projects,
        "fact_daily_activity": n_fact,
        "daily_metrics_days": n_days,
        "window_days": window_days,
        "duration_s": round(time.monotonic() - started, 2),
    }
    logger.info("ETL complete: %s", summary)
    return summary


def freshness():
    """Warehouse freshness for the admin dashboard. Never raises."""
    try:
        last = (db.session.query(func.max(DwDailyMetrics.loaded_at)).scalar())
        return {
            "last_loaded_at": last,
            "dim_user_rows": DwDimUser.query.count(),
            "dim_project_rows": DwDimProject.query.count(),
            "fact_rows": DwFactDailyActivity.query.count(),
            "metric_days": DwDailyMetrics.query.count(),
        }
    except Exception:
        logger.exception("warehouse freshness check failed")
        return None
