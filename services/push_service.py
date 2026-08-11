"""Web Push (VAPID) delivery.

`notify_user` fans a payload out to every browser a user has subscribed. It is
best-effort: it is a no-op when VAPID keys aren't configured, never raises into
the caller, and prunes subscriptions the push service reports as gone (404/410).
"""
from __future__ import annotations

import json
import logging

from flask import current_app

from extensions import db
from models import PushSubscription

logger = logging.getLogger(__name__)


def push_enabled() -> bool:
    return bool(
        current_app.config.get("VAPID_PRIVATE_KEY")
        and current_app.config.get("VAPID_PUBLIC_KEY")
    )


def notify_user(user_id: int, title: str, body: str,
                url: str = "/dashboard", tag: str | None = None) -> int:
    """Send a push to all of the user's subscriptions. Returns count delivered."""
    if not user_id or not push_enabled():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push skipped")
        return 0

    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subs:
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    private_key = current_app.config["VAPID_PRIVATE_KEY"]
    subject = current_app.config.get("VAPID_SUBJECT", "mailto:admin@example.com")

    delivered, dead = 0, []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                timeout=10,
            )
            delivered += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):          # subscription is gone for good
                dead.append(sub)
            else:
                logger.warning("web push failed (%s)", status)
        except Exception as e:                 # network / encoding — don't crash
            logger.warning("web push error: %s", e)

    for sub in dead:
        db.session.delete(sub)
    if dead:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return delivered
