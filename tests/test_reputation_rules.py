"""Server-side reputation rules (services/reputation.py).

Reviews and endorsements are the platform's track record, so the rules must
hold on the server for every write path — not only in which forms the
profile page renders.
"""
from extensions import db
from models import Endorsement, Feedback, ProjectMember


def _teammates(app, make_project, owner_id, other_id, status="completed"):
    """A project with both users as active members; returns its id."""
    pid = make_project(owner_id, status=status)
    with app.app_context():
        db.session.add(ProjectMember(project_id=pid, user_id=owner_id))
        db.session.add(ProjectMember(project_id=pid, user_id=other_id))
        db.session.commit()
    return pid


def _count(app, model, **filters):
    with app.app_context():
        return model.query.filter_by(**filters).count()


def test_review_rejected_without_shared_completed_project(app, client, make_user, login):
    a = make_user("rev-a@example.com")
    b = make_user("rev-b@example.com")
    login("rev-a@example.com")
    client.post(f"/user/{b}/review", data={"rating": "1", "comment": "never worked with them"})
    assert _count(app, Feedback, giver_id=a, receiver_id=b) == 0


def test_review_rejected_while_shared_project_is_unfinished(app, client, make_user, make_project, login):
    a = make_user("rev-c@example.com")
    b = make_user("rev-d@example.com")
    _teammates(app, make_project, a, b, status="open")
    login("rev-c@example.com")
    client.post(f"/user/{b}/review", data={"rating": "5", "comment": "great so far, truly"})
    assert _count(app, Feedback, giver_id=a, receiver_id=b) == 0


def test_review_accepted_after_completed_project_and_linked_to_it(app, client, make_user, make_project, login):
    a = make_user("rev-e@example.com")
    b = make_user("rev-f@example.com")
    pid = _teammates(app, make_project, a, b)
    login("rev-e@example.com")
    client.post(f"/user/{b}/review", data={"rating": "4", "comment": "reliable and on time"})
    with app.app_context():
        feedback = Feedback.query.filter_by(giver_id=a, receiver_id=b).one()
        assert feedback.project_id == pid


def test_profile_shows_forms_only_to_completed_teammates(app, client, make_user, make_project, login):
    me = make_user("view-a@example.com")
    stranger = make_user("view-b@example.com")
    teammate = make_user("view-c@example.com")
    _teammates(app, make_project, me, teammate)
    login("view-a@example.com")

    html = client.get(f"/user/{stranger}").get_data(as_text=True)
    assert f"/user/{stranger}/review" not in html
    assert f"/user/{stranger}/endorse" not in html

    html = client.get(f"/user/{teammate}").get_data(as_text=True)
    assert f"/user/{teammate}/review" in html
    assert f"/user/{teammate}/endorse" in html


def test_profile_endorse_rejected_without_shared_completed_project(app, client, make_user, login):
    a = make_user("end-a@example.com")
    b = make_user("end-b@example.com")
    login("end-a@example.com")
    client.post(f"/user/{b}/endorse", data={"skill": "Python"})
    assert _count(app, Endorsement, giver_id=a, receiver_id=b) == 0


def test_endorse_api_rejects_duplicates_case_insensitively(app, client, make_user, make_project, login):
    a = make_user("end-c@example.com")
    b = make_user("end-d@example.com")
    _teammates(app, make_project, a, b)
    login("end-c@example.com")
    first = client.post("/projects/endorse", json={"user_id": b, "skill": "Python"})
    again = client.post("/projects/endorse", json={"user_id": b, "skill": "python"})
    assert first.status_code == 201
    assert again.status_code == 400
    assert _count(app, Endorsement, giver_id=a, receiver_id=b) == 1


def test_profile_and_api_endorse_share_one_duplicate_rule(app, client, make_user, make_project, login):
    a = make_user("end-e@example.com")
    b = make_user("end-f@example.com")
    _teammates(app, make_project, a, b)
    login("end-e@example.com")
    client.post(f"/user/{b}/endorse", data={"skill": "SQL"})
    resp = client.post("/projects/endorse", json={"user_id": b, "skill": "SQL"})
    assert resp.status_code == 400
    assert _count(app, Endorsement, giver_id=a, receiver_id=b) == 1


def test_endorse_api_validates_input(app, client, make_user, make_project, login):
    a = make_user("end-g@example.com")
    b = make_user("end-h@example.com")
    _teammates(app, make_project, a, b)
    login("end-g@example.com")
    assert client.post("/projects/endorse", json={"user_id": "x", "skill": "Go"}).status_code == 400
    assert client.post("/projects/endorse", json={"user_id": b, "skill": "x" * 81}).status_code == 400
    assert client.post("/projects/endorse", json={"user_id": a, "skill": "Go"}).status_code == 400
    assert _count(app, Endorsement, giver_id=a) == 0
