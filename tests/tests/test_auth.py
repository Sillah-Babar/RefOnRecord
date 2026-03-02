"""Tests for authentication endpoints (login / logout)."""
import pytest

from tests.conftest import make_project


class TestLogin:
    """POST /api/auth/login/"""

    def test_login_success(self, client, registered_user):
        resp = client.post(
            "/api/auth/login/",
            json={"email": "alice@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert "user_id" in data
        assert "expires_at" in data

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post(
            "/api/auth/login/",
            json={"email": "alice@example.com", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    def test_login_unknown_email(self, client, registered_user):
        resp = client.post(
            "/api/auth/login/",
            json={"email": "nobody@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 401

    def test_login_missing_field(self, client, registered_user):
        resp = client.post(
            "/api/auth/login/",
            json={"email": "alice@example.com"},
        )
        assert resp.status_code == 400

    def test_login_not_json(self, client, registered_user):
        resp = client.post("/api/auth/login/", data="notjson", content_type="text/plain")
        assert resp.status_code == 400

    def test_login_extra_field(self, client, registered_user):
        resp = client.post(
            "/api/auth/login/",
            json={"email": "alice@example.com", "password": "securepass123", "extra": "x"},
        )
        assert resp.status_code == 400


class TestLogout:
    """DELETE /api/auth/logout/"""

    def test_logout_success(self, client, auth_headers):
        resp = client.delete("/api/auth/logout/", headers=auth_headers)
        assert resp.status_code == 204

    def test_logout_no_token(self, client):
        resp = client.delete("/api/auth/logout/")
        assert resp.status_code == 401

    def test_logout_invalid_token(self, client):
        resp = client.delete(
            "/api/auth/logout/",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401

    def test_logout_token_invalidated(self, client, auth_headers):
        """After logout the same token must be rejected."""
        client.delete("/api/auth/logout/", headers=auth_headers)
        resp = client.delete("/api/auth/logout/", headers=auth_headers)
        assert resp.status_code == 401
