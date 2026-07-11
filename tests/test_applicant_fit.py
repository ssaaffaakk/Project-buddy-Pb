"""Tests for applicant→project fit scoring (services/applicant_fit.py)."""
from extensions import db
from models import (
    Application, Project, ProjectSkill, ProjectTag, User, UserCourse,
    UserInterest, UserSkill,
)
from services.applicant_fit import score_applicant


def _user(app, email, *, skills=(), interests=(), courses=()):
    with app.app_context():
        u = User(first_name="A", last_name=email[:3], email=email, role="student")
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


def _project(app, owner_id, *, skills=(), tags=(), course=None):
    with app.app_context():
        p = Project(title="P", description="x", owner_id=owner_id, team_size=4,
                    status="open", course=course)
        db.session.add(p)
        db.session.flush()
        for s in skills:
            db.session.add(ProjectSkill(project_id=p.id, skill=s))
        for t in tags:
            db.session.add(ProjectTag(project_id=p.id, tag=t))
        db.session.commit()
        return p.id


def test_strong_applicant_scores_high_with_reasons(app):
    owner = _user(app, "owner@x.com")
    strong = _user(app, "strong@x.com", skills=["python", "react"],
                   courses=["CS101"], interests=["machine learning"])
    pid = _project(app, owner, skills=["python", "react"], tags=["ai / ml"],
                   course="CS101")
    with app.app_context():
        applicant = db.session.get(User, strong)
        project = db.session.get(Project, pid)
        fit = score_applicant(applicant, project)
        assert fit["percent"] >= 80
        assert any("required skill" in r for r in fit["reasons"])
        assert any("took this course" in r for r in fit["reasons"])
        assert "python" in fit["shared_skills"]


def test_weak_applicant_scores_low(app):
    owner = _user(app, "owner2@x.com")
    weak = _user(app, "weak@x.com", skills=["welding"])
    pid = _project(app, owner, skills=["python", "react"], tags=["ai / ml"])
    with app.app_context():
        fit = score_applicant(db.session.get(User, weak), db.session.get(Project, pid))
        assert fit["percent"] <= 30
        assert fit["reasons"] == ["no overlapping skills or interests"]


def test_percent_bounded(app):
    owner = _user(app, "owner3@x.com")
    empty = _user(app, "empty@x.com")
    pid = _project(app, owner)
    with app.app_context():
        fit = score_applicant(db.session.get(User, empty), db.session.get(Project, pid))
        assert 8 <= fit["percent"] <= 99


def test_my_projects_page_shows_fit(app, client, make_user, login):
    owner = make_user("fitowner@example.com")
    with app.app_context():
        p = Project(title="Fit Project", description="x", owner_id=owner,
                    team_size=4, status="open")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectSkill(project_id=p.id, skill="python"))
        applicant = User(first_name="App", last_name="Lee",
                         email="fitapplicant@example.com", role="student")
        applicant.set_password("Test1234!")
        db.session.add(applicant)
        db.session.flush()
        db.session.add(UserSkill(user_id=applicant.id, skill="python"))
        db.session.add(Application(project_id=p.id, applicant_id=applicant.id,
                                   status="pending"))
        db.session.commit()

    login("fitowner@example.com")
    html = client.get("/my-projects").get_data(as_text=True)
    assert "fit" in html.lower()
    assert "required skill" in html
