"""
Per-user contribution statistics.

Aggregates a user's visible collaboration activity — project + study-group
messages, community posts/comments, files shared, and voice sessions — into a
small set of counts shown on their public profile. This makes contribution
history visible (the platform's answer to the free-rider problem) instead of
invisible.

All counts via single aggregate queries (no per-row Python loops). Voice
sessions come from the ActivityEvent stream, so they only reflect activity
since instrumentation shipped — labeled accordingly in the UI.
"""

import logging

from sqlalchemy import func

from extensions import db
from models import (
    ActivityEvent,
    CommunityComment,
    CommunityPost,
    ProjectMessage,
    SharedFile,
    StudyGroupMessage,
)

logger = logging.getLogger(__name__)


def _count(model, **filters):
    return (db.session.query(func.count(model.id)).filter_by(**filters).scalar()) or 0


def contribution_stats(user_id):
    """Return the profile contribution counts for a user. Never raises."""
    try:
        project_msgs = _count(ProjectMessage, sender_id=user_id)
        group_msgs = _count(StudyGroupMessage, author_id=user_id)
        posts = _count(CommunityPost, author_id=user_id)
        comments = _count(CommunityComment, author_id=user_id)
        files = _count(SharedFile, uploader_id=user_id)
        voice_sessions = (db.session.query(func.count(ActivityEvent.id))
                          .filter(ActivityEvent.user_id == user_id,
                                  ActivityEvent.event == "voice_join")
                          .scalar()) or 0
        return {
            "messages": project_msgs + group_msgs,
            "posts": posts + comments,
            "files": files,
            "voice_sessions": voice_sessions,
            "total": project_msgs + group_msgs + posts + comments + files,
        }
    except Exception:
        logger.exception("contribution_stats failed for user %s", user_id)
        return {"messages": 0, "posts": 0, "files": 0, "voice_sessions": 0, "total": 0}
