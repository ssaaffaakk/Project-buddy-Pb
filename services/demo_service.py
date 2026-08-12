"""
Demo sandbox service — creates isolated, time-limited demo accounts.

Each visitor gets a dedicated sandbox user seeded with enough data for
every major feature to be populated (recommendations, kanban, notifications).
Sandboxes expire after DEMO_TTL_HOURS and are purged by a periodic task.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from extensions import db
from models import (
    Application,
    Notification,
    Project,
    ProjectMember,
    ProjectMessage,
    ProjectSkill,
    ProjectTag,
    ProjectTask,
    User,
    UserCourse,
    UserInterest,
    UserSkill,
)

logger = logging.getLogger(__name__)

DEMO_PROFILES = [
    {
        "first_name": "Deniz",
        "last_name": "Yilmaz",
        "department": "Computer Engineering",
        "bio": "Full-stack developer interested in campus tools and ML.",
        "interests": ["Python", "React", "Machine Learning", "Cloud Computing", "Data Analysis"],
        "skills": [
            ("Python", "advanced"), ("React", "intermediate"),
            ("SQL / Database", "intermediate"), ("REST API", "intermediate"),
            ("Machine Learning", "beginner"),
        ],
        "courses": ["CS401 - Software Engineering", "CS415 - Machine Learning"],
    },
]


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_demo_sandbox():
    """Create and return a fully seeded demo User.

    The sandbox is self-contained: the user has skills/interests/courses
    (so the recommender has input), memberships in existing mock projects,
    a personal project with tasks, some applications, and notifications.
    """
    now = _utcnow()
    ttl = current_app.config.get("DEMO_TTL_HOURS", 24)
    suffix = current_app.config.get("DEMO_EMAIL_SUFFIX", "@demo.projectbuddy.local")
    profile = DEMO_PROFILES[0]

    token = secrets.token_hex(8)
    email = f"demo-{token}{suffix}"

    user = User(
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        email=email,
        role="student",
        department=profile["department"],
        bio=profile["bio"],
        onboarded=True,
        is_active=True,
        is_demo=True,
        demo_expires_at=now + timedelta(hours=ttl),
        created_at=now - timedelta(days=30),
    )
    user.set_password(secrets.token_hex(32))
    db.session.add(user)
    db.session.flush()

    _seed_profile(user, profile, now)
    _seed_project_memberships(user, now)
    _seed_own_project(user, now)
    _seed_notifications(user, now)

    db.session.commit()
    return user


def _seed_profile(user, profile, now):
    for tag in profile["interests"]:
        db.session.add(UserInterest(user_id=user.id, tag=tag))
    for skill, level in profile["skills"]:
        db.session.add(UserSkill(user_id=user.id, skill=skill, level=level))
    for course in profile["courses"]:
        db.session.add(UserCourse(user_id=user.id, course=course))


def _seed_project_memberships(user, now):
    """Add the demo user as a member of 2 open mock projects."""
    open_projects = (
        Project.query
        .join(User, Project.owner_id == User.id)
        .filter(
            Project.status == "open",
            User.email.like("%@mock.projectbuddy.local"),
        )
        .limit(2)
        .all()
    )
    for project in open_projects:
        existing = ProjectMember.query.filter_by(
            project_id=project.id, user_id=user.id,
        ).first()
        if not existing:
            db.session.add(ProjectMember(
                project_id=project.id, user_id=user.id,
                role="member", joined_at=now - timedelta(days=5),
            ))


def _seed_own_project(user, now):
    """Give the demo user their own project with kanban tasks."""
    project = Project(
        title="My Demo Project",
        description="A sample project to explore ProjectBuddy features.",
        owner_id=user.id,
        status="open",
        team_size=3,
        course="CS401 - Software Engineering",
        created_at=now - timedelta(days=7),
        deadline=now + timedelta(days=14),
    )
    db.session.add(project)
    db.session.flush()

    for tag in ["Frontend", "Backend", "Data"]:
        db.session.add(ProjectTag(project_id=project.id, tag=tag))
    for skill in ["Python", "React", "SQL / Database"]:
        db.session.add(ProjectSkill(project_id=project.id, skill=skill))

    db.session.add(ProjectMember(
        project_id=project.id, user_id=user.id,
        role="owner", joined_at=now - timedelta(days=7),
    ))

    tasks = [
        ("Set up Flask backend", "done", None),
        ("Design database schema", "done", None),
        ("Build recommendation API", "in_progress", user.id),
        ("Create project detail page", "in_progress", user.id),
        ("Write unit tests", "todo", None),
        ("Deploy to Render", "todo", None),
    ]
    for title, status, assignee_id in tasks:
        db.session.add(ProjectTask(
            project_id=project.id, title=title,
            status=status, assignee_id=assignee_id,
            created_by=user.id,
            created_at=now - timedelta(days=3),
        ))

    db.session.add(ProjectMessage(
        project_id=project.id, sender_id=user.id,
        content="Welcome to the demo project!",
        created_at=now - timedelta(days=6),
    ))

    _seed_applications(project, now)


def _seed_applications(project, now):
    """Add mock users as applicants to the demo user's project."""
    from sqlalchemy import or_
    mock_students = (
        User.query
        .filter(
            User.email.like("%@mock.projectbuddy.local"),
            User.role == "student",
            or_(User.is_demo.is_(None), User.is_demo == False),  # noqa: E712
        )
        .limit(2)
        .all()
    )
    messages = [
        "I'd love to help with the frontend side of this.",
        "I can handle the data pipeline and testing.",
    ]
    for i, student in enumerate(mock_students):
        db.session.add(Application(
            project_id=project.id,
            applicant_id=student.id,
            message=messages[i % len(messages)],
            status="pending",
            created_at=now - timedelta(days=2, hours=i),
        ))


def _seed_notifications(user, now):
    """Pre-fill a few notifications so the bell is not empty."""
    notifs = [
        ("apply", "New application on your demo project", "/projects"),
        ("comment", "Emir commented on Course Planner Rebuild", "/projects"),
        ("system", "Welcome to ProjectBuddy!", "/dashboard"),
    ]
    for ntype, message, link in notifs:
        db.session.add(Notification(
            user_id=user.id, type=ntype, message=message,
            link=link, is_read=False, created_at=now - timedelta(hours=1),
        ))


def purge_expired_demos():
    """Delete expired demo users and ALL their dependent data.

    Run from a periodic task or CLI command. Returns the count of purged users.
    """
    now = _utcnow()
    expired = User.query.filter(
        User.is_demo == True,  # noqa: E712
        User.demo_expires_at <= now,
    ).all()

    if not expired:
        return 0

    count = 0
    for user in expired:
        try:
            _delete_demo_user(user)
            count += 1
        except Exception:
            logger.exception("Failed to purge demo user %s", user.id)
            db.session.rollback()

    return count


def _delete_demo_user(user):
    """Remove a demo user and every row they own across all tables."""
    uid = user.id

    ProjectTask.query.filter_by(assignee_id=uid).update({"assignee_id": None})

    owned_projects = Project.query.filter_by(owner_id=uid).all()
    for project in owned_projects:
        ProjectTask.query.filter_by(project_id=project.id).delete()
        ProjectMessage.query.filter_by(project_id=project.id).delete()
        Application.query.filter_by(project_id=project.id).delete()
        ProjectMember.query.filter_by(project_id=project.id).delete()
        ProjectTag.query.filter_by(project_id=project.id).delete()
        ProjectSkill.query.filter_by(project_id=project.id).delete()
        db.session.delete(project)

    ProjectMember.query.filter_by(user_id=uid).delete()
    Application.query.filter_by(applicant_id=uid).delete()
    ProjectMessage.query.filter_by(sender_id=uid).delete()
    Notification.query.filter_by(user_id=uid).delete()
    UserInterest.query.filter_by(user_id=uid).delete()
    UserSkill.query.filter_by(user_id=uid).delete()
    UserCourse.query.filter_by(user_id=uid).delete()

    from models import (
        ActivityEvent, ChatbotSession, Conversation, DirectMessage,
        DmAttachment, Endorsement, Feedback, MessageReaction,
        ProfileComment, ProfileCommentLike, SavedPost, SavedProject,
        StudyGroupMember, UserAvailability, UserBadge,
    )
    ActivityEvent.query.filter_by(user_id=uid).delete()
    ChatbotSession.query.filter_by(user_id=uid).delete()
    UserBadge.query.filter_by(user_id=uid).delete()
    SavedProject.query.filter_by(user_id=uid).delete()
    SavedPost.query.filter_by(user_id=uid).delete()
    UserAvailability.query.filter_by(user_id=uid).delete()
    StudyGroupMember.query.filter_by(user_id=uid).delete()
    Endorsement.query.filter(
        (Endorsement.giver_id == uid) | (Endorsement.receiver_id == uid),
    ).delete(synchronize_session="fetch")
    Feedback.query.filter(
        (Feedback.giver_id == uid) | (Feedback.receiver_id == uid),
    ).delete(synchronize_session="fetch")
    ProfileCommentLike.query.filter_by(user_id=uid).delete()
    ProfileComment.query.filter_by(user_id=uid).delete()
    MessageReaction.query.filter_by(user_id=uid).delete()
    DirectMessage.query.filter_by(sender_id=uid).delete()
    DmAttachment.query.filter_by(uploader_id=uid).delete()
    Conversation.query.filter(
        (Conversation.user_a_id == uid) | (Conversation.user_b_id == uid),
    ).delete(synchronize_session="fetch")

    db.session.delete(user)
    db.session.commit()
