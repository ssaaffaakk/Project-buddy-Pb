"""
Demo sandbox routes — one-click access to a fully populated trial account.
"""

import functools
import logging

from flask import Blueprint, abort, current_app, flash, redirect, url_for
from flask_login import current_user, login_user

from extensions import limiter

logger = logging.getLogger(__name__)

demo_bp = Blueprint("demo", __name__)

DEMO_BLOCKED_ENDPOINTS = frozenset({
    # Outbound messaging — demo users must not contact real users
    "messages.send",
    "messages.share_post",
    "main.send_project_message",
    "main.post_wall_comment",
    "study_groups.send_message",
    "chat.send_message",
    "chat.start_chat",
    # Reports — prevent spam reports from throwaway accounts
    "users.report_user",
    "users.report_project",
    "main.report_issue",
    "main.report_wall_comment",
    # File uploads
    "main.upload_avatar",
    "community.new_post",
    "study_groups.upload_file",
    # Actions that modify real users' data
    "community.add_comment",
    "projects.create_project",
    "study_groups.create_group",
    "study_groups.join_group",
    "main.apply_to_project",
    "projects.apply",
    "api_v1.apply_to_project",
    "main.submit_endorse",
    "main.submit_review",
    "projects.endorse_skill",
    "projects.submit_feedback",
})


def is_demo_user():
    return current_user.is_authenticated and getattr(current_user, "is_demo", False)


def block_demo(f):
    """Decorator that prevents demo users from calling the wrapped endpoint."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if is_demo_user():
            flash("This action is not available in demo mode.", "warning")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return wrapper


@demo_bp.before_app_request
def _enforce_demo_restrictions():
    """Block demo users from sensitive endpoints globally."""
    if not is_demo_user():
        return None
    from flask import request
    if request.endpoint in DEMO_BLOCKED_ENDPOINTS:
        flash("This action is not available in demo mode.", "warning")
        return redirect(url_for("main.dashboard"))
    return None


@demo_bp.route("/demo")
@limiter.limit(lambda: current_app.config.get("DEMO_RATE_LIMIT", "5 per hour"))
def enter_demo():
    """Create a fresh demo sandbox and log the visitor in."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    from services.demo_service import create_demo_sandbox, purge_expired_demos

    try:
        purge_expired_demos()
    except Exception:
        logger.exception("Lazy demo purge failed")

    try:
        user = create_demo_sandbox()
    except Exception:
        logger.exception("Demo sandbox creation failed")
        flash("Could not create demo account. Please try again.", "error")
        return redirect(url_for("main.index"))

    login_user(user)
    return redirect(url_for("main.dashboard"))
