"""Demo sandbox seeding tests.

The dev/test database is SQLite, which ignores VARCHAR length limits, but
production PostgreSQL enforces them — a seeded value one character too long
crashes demo creation only in production. These tests walk every seeded row
so that class of bug fails in CI instead.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from extensions import db
from models import (
    AdminMessage,
    CommunityLike,
    CommunityPost,
    Conversation,
    DirectMessage,
    DmAttachment,
    MessageReaction,
    ProfileComment,
    ProfileCommentLike,
    ProjectMember,
    ProjectTask,
    ProjectVote,
    PushSubscription,
    Report,
    SavedPost,
    SavedProject,
    User,
)
from services.demo_service import create_demo_sandbox, purge_expired_demos


def test_demo_sandbox_creates_user(app):
    with app.app_context():
        user = create_demo_sandbox()
        assert user.id is not None
        assert user.is_demo is True
        assert user.demo_expires_at is not None
        assert User.query.filter_by(id=user.id).count() == 1


def test_demo_task_statuses_are_valid_kanban_values(app):
    """The board only renders todo | doing | done — anything else vanishes
    from the kanban (and 'in_progress' overflows the String(10) column)."""
    with app.app_context():
        create_demo_sandbox()
        statuses = {t.status for t in ProjectTask.query.all()}
        assert statuses, "demo seed created no kanban tasks"
        assert statuses <= {"todo", "doing", "done"}


def test_demo_seed_fits_string_column_limits(app):
    """Every string the seed writes must fit its column's declared length,
    or PostgreSQL raises StringDataRightTruncation in production."""
    from sqlalchemy import String

    with app.app_context():
        create_demo_sandbox()
        for mapper in db.Model.registry.mappers:
            model = mapper.class_
            limited = [
                col for col in mapper.columns
                if isinstance(col.type, String) and col.type.length
            ]
            if not limited:
                continue
            for row in db.session.query(model).all():
                for col in limited:
                    value = getattr(row, col.key, None)
                    if isinstance(value, str):
                        assert len(value) <= col.type.length, (
                            f"{model.__name__}.{col.key} = {value!r} "
                            f"({len(value)} chars) exceeds String({col.type.length})"
                        )


def test_purge_removes_expired_demo_and_everything_pointing_at_it(app, make_user, make_project):
    """Purge must actually delete the account (it used to fail on a wrong
    column and silently return 0), and must do it in an order PostgreSQL's
    foreign keys accept — so this runs with SQLite FK enforcement switched on."""
    other = make_user("real-user@example.com")
    other_project = make_project(other)
    with app.app_context():
        demo = create_demo_sandbox()
        uid = demo.id
        demo_project = demo.projects_owned[0].id
        post = CommunityPost(author_id=other, body="hello feed")
        db.session.add(post)
        db.session.flush()
        wall = ProfileComment(profile_id=uid, author_id=other, body="welcome!")
        db.session.add(wall)
        a, b = Conversation.pair(uid, other)
        conv = Conversation(user_a_id=a, user_b_id=b)
        db.session.add(conv)
        db.session.flush()
        att = DmAttachment(conversation_id=conv.id, uploader_id=other,
                           filename="notes.pdf", stored_name="x.pdf")
        db.session.add(att)
        db.session.flush()
        dm = DirectMessage(conversation_id=conv.id, sender_id=other, body="hi", attachment_id=att.id)
        db.session.add(dm)
        db.session.add(DirectMessage(conversation_id=conv.id, sender_id=uid, body="hey"))
        db.session.flush()
        db.session.add_all([
            ProjectMember(project_id=other_project, user_id=uid),
            ProjectTask(project_id=other_project, title="demo task", created_by=uid),
            ProjectVote(project_id=other_project, user_id=uid, direction="up"),
            ProjectVote(project_id=demo_project, user_id=other, direction="up"),
            SavedProject(user_id=other, project_id=demo_project),
            Report(reporter_id=other, target_project_id=demo_project, reason="spam"),
            CommunityLike(post_id=post.id, user_id=uid),
            SavedPost(user_id=uid, post_id=post.id),
            ProfileCommentLike(comment_id=wall.id, user_id=other),
            MessageReaction(scope="dm", message_id=dm.id, user_id=uid, emoji="👍"),
            MessageReaction(scope="dm", message_id=dm.id, user_id=other, emoji="❤️"),
            AdminMessage(user_id=uid, sender_id=other, content="please behave"),
            PushSubscription(user_id=uid, endpoint="https://push.example/1", p256dh="k", auth="a"),
        ])
        demo.demo_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        db.session.commit()

        db.session.execute(text("PRAGMA foreign_keys=ON"))
        try:
            assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert purge_expired_demos() == 1
        finally:
            db.session.rollback()
            db.session.execute(text("PRAGMA foreign_keys=OFF"))

        assert db.session.get(User, uid) is None
        assert Conversation.query.count() == 0
        assert DmAttachment.query.count() == 0
        assert ProjectTask.query.filter_by(created_by=uid).count() == 0
        assert ProfileComment.query.count() == 0
        assert MessageReaction.query.count() == 0
        # the real user's own content survives
        assert db.session.get(User, other) is not None
        assert CommunityPost.query.count() == 1
        assert ProjectVote.query.filter_by(user_id=other).count() == 0  # was on the demo's project
