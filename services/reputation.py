"""
Reputation rules — the single source of truth for who may review or endorse
whom.

Reviews and endorsements are the platform's track record, so the rules are
enforced here, server-side, and every route that writes them (the profile
forms and the JSON endpoint) calls these functions. The profile page uses the
same functions to decide which forms to show, so the UI and the server can't
disagree about the rules.

Each *_error() helper returns a user-facing message when the action is not
allowed, or None when it is.
"""

from sqlalchemy import func

from extensions import db
from models import Endorsement, Feedback, Project, ProjectMember

MAX_SKILL_LEN = 80   # Endorsement.skill is String(80)


def shared_completed_project_id(user_a_id, user_b_id):
    """Id of a completed project both users were active members of, or None."""
    theirs = (db.session.query(ProjectMember.project_id)
              .filter(ProjectMember.user_id == user_b_id,
                      ProjectMember.removed == False))  # noqa: E712
    row = (db.session.query(ProjectMember.project_id)
           .join(Project, Project.id == ProjectMember.project_id)
           .filter(ProjectMember.user_id == user_a_id,
                   ProjectMember.removed == False,  # noqa: E712
                   Project.status == "completed",
                   ProjectMember.project_id.in_(theirs))
           .first())
    return row[0] if row else None


def review_error(giver_id, receiver_id):
    """Why `giver` may not leave a profile review for `receiver`, or None."""
    if giver_id == receiver_id:
        return "You cannot review yourself."
    if shared_completed_project_id(giver_id, receiver_id) is None:
        return "You can only review someone you have completed a project with."
    if Feedback.query.filter_by(giver_id=giver_id, receiver_id=receiver_id).first():
        return "You have already reviewed this user."
    return None


def endorsement_error(giver_id, receiver_id, skill):
    """Why `giver` may not endorse `receiver` for `skill`, or None.

    Duplicates are matched case-insensitively, so "Python" and "python" count
    as the same endorsement.
    """
    skill = (skill or "").strip()
    if not skill:
        return "Skill is required."
    if len(skill) > MAX_SKILL_LEN:
        return f"Skill name is too long (max {MAX_SKILL_LEN} characters)."
    if giver_id == receiver_id:
        return "You cannot endorse yourself."
    if shared_completed_project_id(giver_id, receiver_id) is None:
        return "You can only endorse someone you have completed a project with."
    duplicate = Endorsement.query.filter(
        Endorsement.giver_id == giver_id,
        Endorsement.receiver_id == receiver_id,
        func.lower(Endorsement.skill) == skill.lower(),
    ).first()
    if duplicate:
        return f"You already endorsed '{skill}' for this user."
    return None
