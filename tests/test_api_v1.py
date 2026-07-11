"""Tests for the JSON API (/api/v1): JWT auth, pagination, write protection."""
import pytest

from extensions import db
from models import Application, Project, ProjectTag


@pytest.fixture
def token(client, make_user):
    """Factory: register a user (if needed) and return a Bearer token."""
    def _token(email, password="Test1234!"):
        resp = client.post("/api/v1/auth/token",
                           json={"email": email, "password": password})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()["access_token"]
    return _token


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Token issuing ───────────────────────────────────────────────────────────────

def test_token_with_valid_credentials(client, make_user, token):
    make_user("api@example.com")
    resp = client.post("/api/v1/auth/token",
                       json={"email": "api@example.com", "password": "Test1234!"})
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"].count(".") == 2  # JWT shape


def test_token_rejects_bad_password(client, make_user):
    make_user("api2@example.com")
    resp = client.post("/api/v1/auth/token",
                       json={"email": "api2@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_token_validates_payload(client):
    resp = client.post("/api/v1/auth/token", json={"email": "not-an-email"})
    assert resp.status_code == 422  # schema validation, not a 500


# ── Auth gating ─────────────────────────────────────────────────────────────────

def test_reads_require_auth(client):
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/api/v1/me").status_code == 401


def test_reads_accept_session(client, make_user, login):
    make_user("sess@example.com")
    login("sess@example.com")
    assert client.get("/api/v1/projects").status_code == 200


def test_writes_reject_session_require_bearer(client, make_user, make_project, login, token):
    """Session cookie must NOT authorize writes (CSRF-exempt blueprint)."""
    owner = make_user("owner-api@example.com")
    make_user("writer@example.com")
    pid = make_project(owner)

    login("writer@example.com")
    resp = client.post(f"/api/v1/projects/{pid}/apply", json={})
    assert resp.status_code == 401

    tok = token("writer@example.com")
    resp = client.post(f"/api/v1/projects/{pid}/apply", json={}, headers=_auth(tok))
    assert resp.status_code == 201


# ── Projects ────────────────────────────────────────────────────────────────────

def test_projects_pagination_and_filters(app, client, make_user, make_project, token):
    owner = make_user("pag@example.com")
    for i in range(3):
        make_project(owner, title=f"Alpha Project {i}")
    with app.app_context():
        p = Project.query.filter_by(title="Alpha Project 0").first()
        db.session.add(ProjectTag(project_id=p.id, tag="ai / ml"))
        db.session.commit()

    tok = token("pag@example.com")
    body = client.get("/api/v1/projects?per_page=2", headers=_auth(tok)).get_json()
    assert body["total"] == 3 and body["pages"] == 2 and len(body["items"]) == 2

    body = client.get("/api/v1/projects?tag=ai / ml", headers=_auth(tok)).get_json()
    assert body["total"] == 1 and body["items"][0]["title"] == "Alpha Project 0"

    body = client.get("/api/v1/projects?q=Alpha Project 1", headers=_auth(tok)).get_json()
    assert body["total"] == 1


def test_project_detail_and_404(client, make_user, make_project, token):
    owner = make_user("det@example.com")
    pid = make_project(owner)
    tok = token("det@example.com")

    body = client.get(f"/api/v1/projects/{pid}", headers=_auth(tok)).get_json()
    assert body["id"] == pid
    assert body["spots_left"] == body["team_size"] - body["member_count"]
    assert "vote_score" in body

    assert client.get("/api/v1/projects/999999", headers=_auth(tok)).status_code == 404


def test_apply_rules(app, client, make_user, make_project, token):
    owner = make_user("rules-owner@example.com")
    applicant = make_user("rules-app@example.com")
    pid = make_project(owner)

    owner_tok = token("rules-owner@example.com")
    resp = client.post(f"/api/v1/projects/{pid}/apply", json={}, headers=_auth(owner_tok))
    assert resp.status_code == 400  # own project

    tok = token("rules-app@example.com")
    resp = client.post(f"/api/v1/projects/{pid}/apply",
                       json={"message": "hi"}, headers=_auth(tok))
    assert resp.status_code == 201
    with app.app_context():
        appn = Application.query.filter_by(project_id=pid, applicant_id=applicant).one()
        assert appn.message == "hi"

    resp = client.post(f"/api/v1/projects/{pid}/apply", json={}, headers=_auth(tok))
    assert resp.status_code == 409  # duplicate


# ── Me / recommendations / docs ─────────────────────────────────────────────────

def test_me_returns_own_profile(client, make_user, token):
    make_user("me@example.com")
    tok = token("me@example.com")
    body = client.get("/api/v1/me", headers=_auth(tok)).get_json()
    assert body["email"] == "me@example.com"
    assert "interests" in body and "skills" in body


def test_recommendations_shape(client, make_user, token):
    make_user("rec-api@example.com")
    tok = token("rec-api@example.com")
    body = client.get("/api/v1/recommendations", headers=_auth(tok)).get_json()
    assert "items" in body and "variant" in body


def test_openapi_spec_and_docs_render(client):
    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    paths = spec.get_json()["paths"]
    assert "/api/v1/projects" in paths and "/api/v1/auth/token" in paths
    assert client.get("/api/docs").status_code == 200
