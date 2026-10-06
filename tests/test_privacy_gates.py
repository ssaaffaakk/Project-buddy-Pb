"""Privacy gates: private study groups, the project team chat, and bans.

Each of these used to leak or linger: private groups showed their messages to
any logged-in user, project chats rendered for non-members, and a banned
user's open session kept working until it expired.
"""
from extensions import db
from models import ProjectMember, ProjectMessage, StudyGroup, StudyGroupMember, StudyGroupMessage, User
from services.assistant_tools import search_study_groups


def _group(app, creator_id, private):
    with app.app_context():
        g = StudyGroup(name="Thesis circle", topic="Research", creator_id=creator_id, is_private=private)
        db.session.add(g)
        db.session.flush()
        db.session.add(StudyGroupMember(group_id=g.id, user_id=creator_id, role="admin"))
        db.session.add(StudyGroupMessage(group_id=g.id, author_id=creator_id, body="secret plan"))
        db.session.commit()
        return g.id


def test_private_group_hidden_from_non_members(app, client, make_user, login):
    owner = make_user("pg-owner@example.com")
    make_user("pg-outsider@example.com")
    gid = _group(app, owner, private=True)
    login("pg-outsider@example.com")

    resp = client.get(f"/study-groups/{gid}")
    assert resp.status_code == 404
    assert "secret plan" not in resp.get_data(as_text=True)
    assert client.post(f"/study-groups/{gid}/join").status_code == 403


def test_private_group_open_to_its_members(app, client, make_user, login):
    owner = make_user("pg-owner2@example.com")
    gid = _group(app, owner, private=True)
    login("pg-owner2@example.com")
    resp = client.get(f"/study-groups/{gid}")
    assert resp.status_code == 200
    assert "secret plan" in resp.get_data(as_text=True)


def test_public_group_keeps_guest_view_and_join(app, client, make_user, login):
    owner = make_user("pub-owner@example.com")
    make_user("pub-guest@example.com")
    gid = _group(app, owner, private=False)
    login("pub-guest@example.com")
    assert client.get(f"/study-groups/{gid}").status_code == 200
    assert client.post(f"/study-groups/{gid}/join").status_code == 200


def test_assistant_never_surfaces_private_groups(app, make_user):
    owner = make_user("pg-owner3@example.com")
    _group(app, owner, private=True)
    with app.app_context():
        assert search_study_groups("thesis research") == []


def test_project_chat_visible_to_team_only(app, client, make_user, make_project, login):
    owner = make_user("pc-owner@example.com")
    make_user("pc-outsider@example.com")
    pid = make_project(owner)
    with app.app_context():
        db.session.add(ProjectMember(project_id=pid, user_id=owner))
        db.session.add(ProjectMessage(project_id=pid, sender_id=owner, content="team-only note"))
        db.session.commit()

    login("pc-outsider@example.com")
    html = client.get(f"/project/{pid}").get_data(as_text=True)
    assert "team-only note" not in html
    assert "Only team members can read the project chat." in html

    client.get("/auth/logout")
    login("pc-owner@example.com")
    assert "team-only note" in client.get(f"/project/{pid}").get_data(as_text=True)


def test_ban_ends_an_open_session(app, client, make_user, login):
    uid = make_user("banned-later@example.com")
    login("banned-later@example.com")
    assert client.get("/dashboard").status_code == 200

    with app.app_context():
        db.session.get(User, uid).is_banned = True
        db.session.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
