"""Tests for user CRUD endpoints."""


class TestUserRegistration:
    """POST /api/users/"""

    def test_register_success(self, client):
        resp = client.post(
            "/api/users/",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "password_hash" not in data
        assert "Location" in resp.headers

    def test_register_with_optional_fields(self, client):
        resp = client.post(
            "/api/users/",
            json={
                "email": "opt@example.com",
                "username": "optuser",
                "password": "password123",
                "phone_number": "+1-555-9999",
                "tier": "premium",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["tier"] == "premium"
        assert data["phone_number"] == "+1-555-9999"

    def test_register_duplicate_email(self, client, registered_user):
        resp = client.post(
            "/api/users/",
            json={
                "email": "alice@example.com",
                "username": "different",
                "password": "password123",
            },
        )
        assert resp.status_code == 409

    def test_register_duplicate_username(self, client, registered_user):
        resp = client.post(
            "/api/users/",
            json={
                "email": "different@example.com",
                "username": "alice",
                "password": "password123",
            },
        )
        assert resp.status_code == 409

    def test_register_missing_email(self, client):
        resp = client.post(
            "/api/users/",
            json={"username": "nomail", "password": "password123"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/users/",
            json={"email": "x@x.com", "username": "xuser", "password": "short"},
        )
        assert resp.status_code == 400

    def test_register_not_json(self, client):
        resp = client.post(
            "/api/users/", data="notjson", content_type="text/plain"
        )
        assert resp.status_code == 400

    def test_register_extra_field(self, client):
        resp = client.post(
            "/api/users/",
            json={
                "email": "x@x.com",
                "username": "xuser",
                "password": "password123",
                "hack": "yes",
            },
        )
        assert resp.status_code == 400


class TestGetUser:
    """GET /api/users/<user>/"""

    def test_get_own_profile(self, client, registered_user, auth_headers):
        resp = client.get(f"/api/users/{registered_user}/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "alice"
        assert "links" in data

    def test_get_other_user_forbidden(
        self, client, registered_user, second_registered_user, second_auth_headers
    ):
        resp = client.get(
            f"/api/users/{registered_user}/", headers=second_auth_headers
        )
        assert resp.status_code == 403

    def test_get_nonexistent_user(self, client, auth_headers):
        resp = client.get("/api/users/99999/", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_without_auth(self, client, registered_user):
        resp = client.get(f"/api/users/{registered_user}/")
        assert resp.status_code == 401


class TestUpdateUser:
    """PUT /api/users/<user>/"""

    def test_update_phone(self, client, registered_user, auth_headers):
        resp = client.put(
            f"/api/users/{registered_user}/",
            json={"phone_number": "+44-7700-123456"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["phone_number"] == "+44-7700-123456"

    def test_update_forbidden(
        self, client, registered_user, second_auth_headers
    ):
        resp = client.put(
            f"/api/users/{registered_user}/",
            json={"phone_number": "0"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_update_not_json(self, client, registered_user, auth_headers):
        resp = client.put(
            f"/api/users/{registered_user}/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_update_empty_body(self, client, registered_user, auth_headers):
        resp = client.put(
            f"/api/users/{registered_user}/", json={}, headers=auth_headers
        )
        assert resp.status_code == 400


class TestDeleteUser:
    """DELETE /api/users/<user>/"""

    def test_delete_own_account(self, client, registered_user, auth_headers):
        resp = client.delete(
            f"/api/users/{registered_user}/", headers=auth_headers
        )
        assert resp.status_code == 204

    def test_delete_forbidden(
        self, client, registered_user, second_auth_headers
    ):
        resp = client.delete(
            f"/api/users/{registered_user}/", headers=second_auth_headers
        )
        assert resp.status_code == 403
