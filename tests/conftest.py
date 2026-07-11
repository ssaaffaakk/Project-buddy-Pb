"""Shared pytest fixtures for ProjectBuddy smoke tests.

Uses TestingConfig (in-memory SQLite with a shared StaticPool connection) so
each test gets an isolated, migration-free database. No mock data is seeded.
"""
import pytest

from app import create_app
from config import TestingConfig
from extensions import db as _db, socketio as _socketio
from models import User, Project


@pytest.fixture(scope="session")
def app():
    """One app for the whole session.

    SocketIO is a module-level singleton; creating a fresh app per test would
    re-init it repeatedly and leave the SocketIO test client cross-wired to a
    stale server. A single app keeps init_app to one call. Per-test DB isolation
    is handled by the autouse `_reset_db` fixture below.
    """
    return create_app(TestingConfig)


@pytest.fixture(autouse=True)
def _reset_db(app):
    """Give every test an empty schema (StaticPool → one shared connection)."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
    yield
    with app.app_context():
        _db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def socketio():
    return _socketio


@pytest.fixture
def make_user(app):
    """Factory: create a persisted user, return its id."""
    def _make(email, password="Test1234!", role="student", first="Test", last="User"):
        with app.app_context():
            u = User(first_name=first, last_name=last, email=email.lower(), role=role)
            u.set_password(password)
            _db.session.add(u)
            _db.session.commit()
            return u.id
    return _make


@pytest.fixture
def make_project(app):
    """Factory: create a project owned by owner_id, return its id."""
    def _make(owner_id, title="Test Project", team_size=4, status="open"):
        with app.app_context():
            p = Project(
                title=title,
                description="A project for testing.",
                owner_id=owner_id,
                team_size=team_size,
                status=status,
            )
            _db.session.add(p)
            _db.session.commit()
            return p.id
    return _make


@pytest.fixture
def login(client):
    """Log a user in via the real /auth/login endpoint (session cookie set)."""
    def _login(email, password="Test1234!"):
        return client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
    return _login
