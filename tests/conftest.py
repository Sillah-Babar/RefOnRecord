"""
Pytest fixtures shared across all test modules.
"""
from unittest.mock import patch

import pytest

from resumeverifier import create_app
from resumeverifier.extensions import db as _db
from resumeverifier.auth import hash_password
from resumeverifier.models import User, ResumeProject, Experience, Session


@pytest.fixture(scope="session")
def app():
    """Create an application instance configured for testing."""
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "CACHE_TYPE": "NullCache",
            "WTF_CSRF_ENABLED": False,
        }
    )
    return application


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean database for every test function."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):  # noqa: W0621 – db fixture intentionally shadows outer name
    """Provide a Flask test client with a fresh database."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def user_data():
    """Raw payload for a valid user registration."""
    return {
        "email": "alice@example.com",
        "username": "alice",
        "password": "securepass123",
        "phone_number": "+1-555-0100",
    }


@pytest.fixture(scope="function")
def second_user_data():
    """Raw payload for a second user (used in ownership tests)."""
    return {
        "email": "bob@example.com",
        "username": "bob",
        "password": "securepass456",
    }


@pytest.fixture(scope="function")
def registered_user(db, app):
    """A pre-created user row in the database."""
    with app.app_context():
        user = User(
            email="alice@example.com",
            username="alice",
            password_hash=hash_password("securepass123"),
            phone_number="+1-555-0100",
            tier="normal",
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return user.user_id


@pytest.fixture(scope="function")
def second_registered_user(db, app):
    """A second pre-created user (for forbidden-access tests)."""
    with app.app_context():
        user = User(
            email="bob@example.com",
            username="bob",
            password_hash=hash_password("securepass456"),
            tier="normal",
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return user.user_id


def _make_token(app, db, user_id):
    """Insert a session token for the given user and return the token string."""
    with app.app_context():
        session = Session(user_id=user_id, token=Session.generate_token())
        db.session.add(session)
        db.session.commit()
        return session.token


@pytest.fixture(scope="function")
def auth_token(app, db, registered_user):
    """Bearer token for ``alice``."""
    return _make_token(app, db, registered_user)


@pytest.fixture(scope="function")
def second_auth_token(app, db, second_registered_user):
    """Bearer token for ``bob``."""
    return _make_token(app, db, second_registered_user)


@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """Authorization header dict for ``alice``."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="function")
def second_auth_headers(second_auth_token):
    """Authorization header dict for ``bob``."""
    return {"Authorization": f"Bearer {second_auth_token}"}


def make_project(app, db, user_id, name="My Resume"):
    """Helper: insert a project and return its project_id."""
    with app.app_context():
        project = ResumeProject(
            user_id=user_id,
            project_name=name,
            template_style="classic",
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project.project_id


def make_experience(app, db, project_id):
    """Helper: insert an experience row and return its experience_id."""
    from datetime import date  # pylint: disable=import-outside-toplevel
    with app.app_context():
        exp = Experience(
            project_id=project_id,
            company_name="Acme Corp",
            position_title="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 12, 31),
            description="Built stuff.",
        )
        db.session.add(exp)
        db.session.commit()
        db.session.refresh(exp)
        return exp.experience_id


def make_vr_direct(client, app, db, user_id, auth_headers):
    """
    Helper: create project + experience + verification request via the API.

    Returns:
        tuple: (experience_id, request_id, verification_token)
    """
    pid = make_project(app, db, user_id)
    eid = make_experience(app, db, pid)
    with patch("resumeverifier.email_service.send_verification_email"):
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            json={
                "verifier_name": "Boss",
                "verifier_position": "Manager",
                "verifier_email": "boss@acme.com",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 201
    data = resp.get_json()
    return eid, data["request_id"], data["verification_token"]
