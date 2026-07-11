"""
Instructor oversight — active projects grouped by course, with team-health flags.

Surfaces the struggling teams a supervisor would otherwise miss: no activity in
days, a deadline closing in with no movement, or already overdue. Health is
derived from the last project message (or creation date) and the deadline.

Read-only aggregation. Intended for an instructor/admin-gated page.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func

from extensions import db
from models import Project, ProjectMember, ProjectMessage

logger = logging.getLogger(__name__)

STALE_DAYS = 7          # no activity for this long → stalled
DEADLINE_SOON_DAYS = 5  # deadline within this many days → at risk


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _health(project, last_activity, now):
    """Return (level, list_of_flags): level ∈ {'ok','watch','risk'}."""
    flags = []
    days_inactive = (now - last_activity).days if last_activity else None
    if days_inactive is not None and days_inactive >= STALE_DAYS:
        flags.append(f"no activity in {days_inactive}d")

    deadline_days = None
    if project.deadline and project.status != "completed":
        deadline_days = (project.deadline - now).days
        if deadline_days < 0:
            flags.append(f"overdue by {abs(deadline_days)}d")
        elif deadline_days <= DEADLINE_SOON_DAYS:
            flags.append(f"deadline in {deadline_days}d")

    overdue = deadline_days is not None and deadline_days < 0
    stalled = days_inactive is not None and days_inactive >= STALE_DAYS
    soon = deadline_days is not None and 0 <= deadline_days <= DEADLINE_SOON_DAYS

    if overdue or (stalled and soon):
        level = "risk"
    elif stalled or soon:
        level = "watch"
    else:
        level = "ok"
    return level, flags, days_inactive, deadline_days


def course_overview():
    """Active projects grouped by course with health. Returns
    [{course, projects: [...], risk_count}, ...] sorted by risk first."""
    now = _now_naive()
    projects = (Project.query
                .filter(Project.status.in_(["open", "closed"]))
                .all())
    if not projects:
        return []

    # last-activity per project in one query (max message timestamp)
    last_msg = dict(db.session.query(
        ProjectMessage.project_id, func.max(ProjectMessage.created_at)
    ).group_by(ProjectMessage.project_id).all())
    member_counts = dict(db.session.query(
        ProjectMember.project_id, func.count(ProjectMember.id)
    ).filter(ProjectMember.removed == False)  # noqa: E712
     .group_by(ProjectMember.project_id).all())

    by_course = {}
    for p in projects:
        last_activity = last_msg.get(p.id) or p.created_at
        level, flags, days_inactive, deadline_days = _health(p, last_activity, now)
        course = p.course or "No course"
        by_course.setdefault(course, []).append({
            "id": p.id,
            "title": p.title,
            "owner": p.owner.get_full_name() if p.owner else "—",
            "status": p.status,
            "members": member_counts.get(p.id, 0),
            "team_size": p.team_size,
            "level": level,
            "flags": flags,
            "days_inactive": days_inactive,
            "deadline_days": deadline_days,
        })

    _rank = {"risk": 0, "watch": 1, "ok": 2}
    overview = []
    for course, items in by_course.items():
        items.sort(key=lambda i: _rank[i["level"]])
        overview.append({
            "course": course,
            "projects": items,
            "risk_count": sum(1 for i in items if i["level"] == "risk"),
            "watch_count": sum(1 for i in items if i["level"] == "watch"),
        })
    overview.sort(key=lambda c: (c["risk_count"], c["watch_count"]), reverse=True)
    return overview
