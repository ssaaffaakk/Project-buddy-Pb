"""Tests for semantic project search + duplicate detection
(services/project_search.py and the /projects/check-similar endpoint)."""
from extensions import db
from models import Project, ProjectTag, User
from services.project_search import semantic_search, similar_projects


def _project(app, title, desc, *, tags=(), status="open"):
    with app.app_context():
        owner = User.query.filter_by(email="ps-owner@x.com").first()
        if owner is None:
            owner = User(first_name="O", last_name="w", email="ps-owner@x.com", role="student")
            owner.set_password("Test1234!")
            db.session.add(owner)
            db.session.flush()
        p = Project(title=title, description=desc, owner_id=owner.id,
                    team_size=4, status=status)
        db.session.add(p)
        db.session.flush()
        for t in tags:
            db.session.add(ProjectTag(project_id=p.id, tag=t))
        db.session.commit()
        return p.id


def test_semantic_search_finds_relevant(app):
    ml = _project(app, "Machine Learning Classifier",
                  "Train a model to classify images", tags=["ai / ml"])
    _project(app, "Cafeteria Menu App", "Daily menu for the campus cafe",
             tags=["mobile"])
    with app.app_context():
        results = semantic_search("machine learning model")
        ids = [p.id for p in results]
        assert ml in ids
        assert ids[0] == ml  # most relevant first


def test_semantic_search_empty_query_returns_open(app):
    _project(app, "A", "x")
    _project(app, "B", "y", status="completed")
    with app.app_context():
        results = semantic_search("")
        assert all(p.status == "open" for p in results)


def test_similar_projects_flags_near_duplicate(app):
    _project(app, "Campus Event Tracker",
             "An app to track campus events and RSVPs", tags=["mobile"])
    with app.app_context():
        similar = similar_projects("Campus Event Tracker",
                                   "App to track campus events and RSVPs")
        assert similar
        assert similar[0]["similarity"] >= 18
        assert similar[0]["url"].startswith("/project/")


def test_similar_projects_ignores_unrelated(app):
    _project(app, "Quantum Chemistry Simulator", "Simulate molecular orbitals")
    with app.app_context():
        similar = similar_projects("Knitting Club Social App",
                                   "Organize knitting meetups")
        assert similar == []


def test_check_similar_endpoint(app, client, make_user, login):
    _project(app, "Study Buddy Finder", "Find people to study with on campus")
    make_user("checker@example.com")
    login("checker@example.com")

    resp = client.post("/projects/check-similar",
                       json={"title": "Study Buddy Finder",
                             "description": "Find people to study with"})
    assert resp.status_code == 200
    assert "similar" in resp.get_json()

    # too-short title → no work, empty result
    short = client.post("/projects/check-similar", json={"title": "ab"})
    assert short.get_json()["similar"] == []


def test_check_similar_requires_login(client):
    resp = client.post("/projects/check-similar", json={"title": "anything here"})
    assert resp.status_code == 302
