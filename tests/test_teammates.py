"""Tests for the teammate finder (services/teammate_service.py + /teammates)."""
from extensions import db
from models import User, UserCourse, UserInterest, UserSkill
from services.teammate_service import find_teammates


def _profile(app, email, *, skills=(), interests=(), courses=(), dept=None, role="student"):
    with app.app_context():
        u = User(first_name="T", last_name=email[:3], email=email, role=role, department=dept)
        u.set_password("Test1234!")
        db.session.add(u)
        db.session.flush()
        for s in skills:
            db.session.add(UserSkill(user_id=u.id, skill=s))
        for i in interests:
            db.session.add(UserInterest(user_id=u.id, tag=i))
        for c in courses:
            db.session.add(UserCourse(user_id=u.id, course=c))
        db.session.commit()
        return u.id


def test_matches_rank_by_shared_signals(app):
    me = _profile(app, "me@x.com", skills=["python", "react"],
                  courses=["CS101"], dept="CS")
    close = _profile(app, "close@x.com", skills=["python", "react"],
                     courses=["CS101"], dept="CS")
    far = _profile(app, "far@x.com", skills=["welding"], dept="Mechanical")

    with app.app_context():
        matches = find_teammates(me)
        ids = [m["user"]["id"] for m in matches]
        assert close in ids
        # the strongly-overlapping user ranks above the unrelated one
        assert ids.index(close) < ids.index(far) if far in ids else True
        top = matches[0]
        assert top["user"]["id"] == close
        assert top["match_percent"] == 99  # best match on the run
        assert any("skill" in r for r in top["reasons"])


def test_excludes_self_admin_and_banned(app):
    me = _profile(app, "self@x.com", skills=["python"])
    _profile(app, "admin@x.com", skills=["python"], role="admin")
    banned = _profile(app, "banned@x.com", skills=["python"])
    with app.app_context():
        db.session.get(User, banned).is_banned = True
        db.session.commit()
        ids = [m["user"]["id"] for m in find_teammates(me)]
        assert me not in ids
        assert all(db.session.get(User, i).role != "admin" for i in ids)
        assert banned not in ids


def test_no_email_leaked(app):
    me = _profile(app, "priv@x.com", skills=["python"])
    _profile(app, "other@x.com", skills=["python"])
    with app.app_context():
        for m in find_teammates(me):
            assert "email" not in m["user"]


def test_page_requires_login_and_renders(app, client, make_user, login):
    assert client.get("/teammates").status_code == 302  # anonymous → login
    make_user("page@example.com")
    login("page@example.com")
    resp = client.get("/teammates")
    assert resp.status_code == 200
    assert "Find Teammates" in resp.get_data(as_text=True)


def test_api_teammates_no_email(app, client, make_user, login):
    make_user("apime@example.com")
    make_user("apiother@example.com")
    login("apime@example.com")
    resp = client.get("/api/v1/teammates")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "items" in body
    for m in body["items"]:
        assert "email" not in m["user"]
