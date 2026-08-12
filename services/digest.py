"""
Weekly recommendation digest.

Once a week, each active student gets their top project match delivered as an
in-app notification (and a web push, if they enabled it) — the recommender
served on a schedule instead of only when they open the dashboard.

Best-effort and idempotent per run: a user who already has an unread digest
notification from the last 6 days is skipped, so a re-run (or an overlapping
schedule) never spams. Nothing here raises into the caller.
"""

import logging
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Notification, User
from services.recommendation_service import get_recommended_projects

logger = logging.getLogger(__name__)

_DEDUPE_DAYS = 6


def _recently_notified(user_id):
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_DEDUPE_DAYS)
    return (Notification.query
            .filter(Notification.user_id == user_id,
                    Notification.type == "digest",
                    Notification.created_at >= since)
            .first() is not None)


def send_weekly_digest(limit_users=None):
    """Deliver the digest to eligible users. Returns a summary dict."""
    from sqlalchemy import or_
    users = (User.query
             .filter(User.role != "admin",
                     User.is_banned == False,     # noqa: E712
                     User.is_active == True,       # noqa: E712
                     or_(User.is_demo.is_(None), User.is_demo == False))  # noqa: E712
             .all())
    if limit_users:
        users = users[:limit_users]

    sent = skipped = 0
    for user in users:
        if _recently_notified(user.id):
            skipped += 1
            continue
        try:
            recs = get_recommended_projects(user.id)
        except Exception:
            logger.exception("digest: recommendation failed for user %s", user.id)
            continue
        if not recs:
            skipped += 1
            continue

        top, fit = recs[0]
        extra = len(recs) - 1
        message = (f"✨ New match: \"{top.title}\" ({round(fit)}% fit)"
                   + (f" +{extra} more projects for you" if extra > 0 else ""))
        link = f"/project/{top.id}"

        db.session.add(Notification(user_id=user.id, type="digest",
                                    message=message, link=link))
        try:
            from services.tasks import dispatch_push
            dispatch_push(user.id, "Your weekly matches", message, url=link)
        except Exception:
            logger.debug("digest push dispatch failed", exc_info=True)
        sent += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("digest commit failed")
        return {"sent": 0, "skipped": skipped, "error": True}

    summary = {"sent": sent, "skipped": skipped, "total_users": len(users)}
    logger.info("weekly digest: %s", summary)
    return summary
