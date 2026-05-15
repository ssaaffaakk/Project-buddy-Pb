from extensions import db
from models import Badge, Endorsement, Project, ProjectMember, User, UserBadge


def check_and_award_badges(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return []

    projects_completed = count_completed_projects(user_id)
    endorsements_received = count_endorsements_received(user_id)
    badge_rules = {
        "first step": projects_completed >= 1,
        "veteran": projects_completed >= 5,
        "expert": endorsements_received >= 10,
    }

    awarded_badges = []
    for badge_name, condition_met in badge_rules.items():
        if not condition_met or already_has_badge(user_id, badge_name):
            continue

        badge = Badge.query.filter_by(name=badge_name).first()
        if badge:
            db.session.add(UserBadge(user_id=user_id, badge_id=badge.id))
            awarded_badges.append(badge_name)

    if awarded_badges:
        db.session.commit()

    return awarded_badges


def count_completed_projects(user_id):
    return (
        ProjectMember.query.join(Project)
        .filter(
            ProjectMember.user_id == user_id,
            Project.status == "completed",
        )
        .count()
    )


def count_endorsements_received(user_id):
    return Endorsement.query.filter_by(receiver_id=user_id).count()


def already_has_badge(user_id, badge_name):
    return (
        db.session.query(UserBadge)
        .join(Badge)
        .filter(
            UserBadge.user_id == user_id,
            Badge.name == badge_name,
        )
        .count()
        > 0
    )
