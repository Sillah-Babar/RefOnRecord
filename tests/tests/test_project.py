"""Tests for resume project endpoints."""
from tests.conftest import make_project


class TestListProjects:
    """GET /api/users/<user>/projects/"""

    def test_list_empty(self, client, registered_user, auth_headers):
        resp = client.get(
            f"/api/users/{registered_user}/projects/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_with_projects(self, client, app, db, registered_user, auth_headers):
        make_project(app, db, registered_user, "Resume A")
        make_project(app, db, registered_user, "Resume B")
        resp = client.get(
            f"/api/users/{registered_user}/projects/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_list_cached_response(self, client, app, db, registered_user, auth_headers):
        """Second identical request hits the cache (same response)."""
        make_project(app, db, registered_user, "Cached")
        resp1 = client.get(
            f"/api/users/{registered_user}/projects/", headers=auth_headers
        )
        resp2 = client.get(
            f"/api/users/{registered_user}/projects/", headers=auth_headers
        )
        assert resp1.status_code == resp2.status_code == 200

    def test_list_forbidden(
        self, client, registered_user, second_auth_headers
    ):
        resp = client.get(
            f"/api/users/{registered_user}/projects/",
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_list_no_auth(self, client, registered_user):
        resp = client.get(f"/api/users/{registered_user}/projects/")
        assert resp.status_code == 401


class TestCreateProject:
    """POST /api/users/<user>/projects/"""

    def test_create_minimal(self, client, registered_user, auth_headers):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            json={"project_name": "My CV"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["project_name"] == "My CV"
        assert data["template_style"] == "classic"
        assert "Location" in resp.headers

    def test_create_full(self, client, registered_user, auth_headers):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            json={
                "project_name": "Full CV",
                "template_style": "modern",
                "linkedin_url": "https://linkedin.com/in/alice",
                "github_url": "https://github.com/alice",
                "is_employed": True,
                "current_company": "Acme",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["template_style"] == "modern"
        assert data["is_employed"] is True

    def test_create_missing_name(self, client, registered_user, auth_headers):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            json={"template_style": "minimal"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_invalid_template(self, client, registered_user, auth_headers):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            json={"project_name": "X", "template_style": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_not_json(self, client, registered_user, auth_headers):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_forbidden(
        self, client, registered_user, second_auth_headers
    ):
        resp = client.post(
            f"/api/users/{registered_user}/projects/",
            json={"project_name": "Hack"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 403


class TestGetProject:
    """GET /api/projects/<project>/"""

    def test_get_own_project(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.get(f"/api/projects/{pid}/", headers=auth_headers)
        assert resp.status_code == 200
        assert "links" in resp.get_json()

    def test_get_cached(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        client.get(f"/api/projects/{pid}/", headers=auth_headers)
        resp = client.get(f"/api/projects/{pid}/", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.get(f"/api/projects/{pid}/", headers=second_auth_headers)
        assert resp.status_code == 403

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/projects/99999/", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateProject:
    """PUT /api/projects/<project>/"""

    def test_update_name(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.put(
            f"/api/projects/{pid}/",
            json={"project_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["project_name"] == "Updated Name"

    def test_update_clears_cache(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        client.get(f"/api/projects/{pid}/", headers=auth_headers)  # populate cache
        client.put(
            f"/api/projects/{pid}/",
            json={"project_name": "New"},
            headers=auth_headers,
        )
        resp = client.get(f"/api/projects/{pid}/", headers=auth_headers)
        assert resp.get_json()["project_name"] == "New"

    def test_update_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.put(
            f"/api/projects/{pid}/",
            json={"project_name": "X"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_update_empty_body(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.put(
            f"/api/projects/{pid}/", json={}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_update_not_json(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.put(
            f"/api/projects/{pid}/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestDeleteProject:
    """DELETE /api/projects/<project>/"""

    def test_delete_own_project(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.delete(f"/api/projects/{pid}/", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_not_found_after(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        client.delete(f"/api/projects/{pid}/", headers=auth_headers)
        resp = client.get(f"/api/projects/{pid}/", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.delete(
            f"/api/projects/{pid}/", headers=second_auth_headers
        )
        assert resp.status_code == 403
