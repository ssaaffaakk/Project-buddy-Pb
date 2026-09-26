"""Demo sandbox seeding tests.

The dev/test database is SQLite, which ignores VARCHAR length limits, but
production PostgreSQL enforces them — a seeded value one character too long
crashes demo creation only in production. These tests walk every seeded row
so that class of bug fails in CI instead.
"""
from extensions import db
from models import ProjectTask, User
from services.demo_service import create_demo_sandbox


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


def test_demo_projects_stay_out_of_shared_pool(app, client, make_user, make_project):
    """A sandbox's seeded project is private to that visitor: it must not show
    up in search/browse, the instructor dashboard, or the JSON API list."""
    from services.instructor_view import course_overview
    from services.project_search import _open_projects_with_tags

    owner = make_user("real-owner@example.com")
    make_project(owner, title="Real Project")
    with app.app_context():
        create_demo_sandbox()

        pool = {p.title for p in _open_projects_with_tags()}
        assert pool == {"Real Project"}

        instructor = {p["title"] for c in course_overview() for p in c["projects"]}
        assert instructor == {"Real Project"}

    tok = client.post("/api/v1/auth/token", json={
        "email": "real-owner@example.com", "password": "Test1234!",
    }).get_json()["access_token"]
    body = client.get("/api/v1/projects",
                      headers={"Authorization": f"Bearer {tok}"}).get_json()
    assert [p["title"] for p in body["items"]] == ["Real Project"]


def test_demo_visitor_can_open_signup_form(client):
    """The banner's "Create a real account" link must render the register
    form — not bounce the still-logged-in sandbox back to the dashboard."""
    assert client.get("/demo").status_code == 302
    resp = client.get("/auth/register")
    assert resp.status_code == 200
    assert 'class="panel active" id="panel-register"' in resp.get_data(as_text=True)


def test_demo_create_project_invites_signup(client):
    """Posting a project from the demo is swapped for a signup invitation."""
    client.get("/demo")
    resp = client.post("/projects/", data={"title": "x"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/auth/register")
