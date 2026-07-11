"""Tests for per-user contribution stats (services/contribution_stats.py)."""
from extensions import db
from models import (
    CommunityPost, Project, ProjectMessage, SharedFile, StudyGroup,
    StudyGroupMessage, User,
)
from services import analytics
from services.contribution_stats import contribution_stats


def test_counts_across_sources(app, make_user):
    uid = make_user("contrib@example.com")
    with app.app_context():
        owner = User.query.get(uid)
        p = Project(title="P", description="x", owner_id=owner.id, team_size=3, status="open")
        g = StudyGroup(name="G", creator_id=owner.id)
        db.session.add_all([p, g])
        db.session.flush()
        db.session.add(ProjectMessage(project_id=p.id, sender_id=uid, content="hi"))
        db.session.add(ProjectMessage(project_id=p.id, sender_id=uid, content="again"))
        db.session.add(StudyGroupMessage(group_id=g.id, author_id=uid, body="yo"))
        db.session.add(CommunityPost(author_id=uid, body="post"))
        db.session.add(SharedFile(group_id=g.id, uploader_id=uid,
                                  filename="a.pdf", stored_name="x.pdf"))
        analytics.track("voice_join", uid, "group", g.id)
        db.session.commit()

        stats = contribution_stats(uid)
        assert stats["messages"] == 3      # 2 project + 1 group
        assert stats["posts"] == 1
        assert stats["files"] == 1
        assert stats["voice_sessions"] == 1
        assert stats["total"] == 5         # excludes voice sessions


def test_zero_for_new_user(app, make_user):
    uid = make_user("quiet@example.com")
    with app.app_context():
        stats = contribution_stats(uid)
        assert stats == {"messages": 0, "posts": 0, "files": 0,
                         "voice_sessions": 0, "total": 0}


def test_profile_shows_contribution_card(app, client, make_user, login):
    make_user("viewer-c@example.com")
    target = make_user("target-c@example.com")
    with app.app_context():
        p = Project(title="P", description="x", owner_id=target, team_size=3, status="open")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMessage(project_id=p.id, sender_id=target, content="hi"))
        db.session.commit()

    login("viewer-c@example.com")
    html = client.get(f"/user/{target}").get_data(as_text=True)
    assert "Contribution activity" in html
