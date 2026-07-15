"""Emoji reactions on messages — shared by DMs and study-group chat.

Generic over message type via a `scope` string ('dm' | 'group') so both
DirectMessage and StudyGroupMessage share one table and one code path. See
models.MessageReaction. A "pill" is one emoji's rollup on a message:
{'emoji', 'count', 'user_ids': [...]}. The viewer decides "mine" by checking
whether their id is in user_ids.
"""

from extensions import db
from models import MessageReaction

# The fixed palette offered in the UI (also the display order of pills).
ALLOWED = ["👍", "❤️", "😂", "🎉", "😮", "😢"]
_ALLOWED_SET = set(ALLOWED)


def is_allowed(emoji):
    return emoji in _ALLOWED_SET


def summarize(scope, message_ids):
    """{message_id: [pill, ...]} for the given ids (empty ids -> {})."""
    ids = list(message_ids)
    if not ids:
        return {}
    rows = (MessageReaction.query
            .filter(MessageReaction.scope == scope,
                    MessageReaction.message_id.in_(ids))
            .all())
    by_msg = {}
    for r in rows:
        by_msg.setdefault(r.message_id, {}).setdefault(r.emoji, []).append(r.user_id)
    out = {}
    for mid, emap in by_msg.items():
        out[mid] = [
            {"emoji": e, "count": len(emap[e]), "user_ids": emap[e]}
            for e in ALLOWED if e in emap
        ]
    return out


def toggle(scope, message_id, user_id, emoji):
    """Add or remove one user's emoji on a message; returns the message's pills."""
    existing = MessageReaction.query.filter_by(
        scope=scope, message_id=message_id, user_id=user_id, emoji=emoji
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(MessageReaction(
            scope=scope, message_id=message_id, user_id=user_id, emoji=emoji
        ))
    db.session.commit()
    return summarize(scope, [message_id]).get(message_id, [])
