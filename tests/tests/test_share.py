"""Tests for share link endpoints."""
from tests.conftest import make_project, make_experience


def make_share(client, project_id, auth_headers, body=None):
    """Helper: create a share link and return the response JSON."""
    resp = client.post(
        f"/api/projects/{project_id}/shares/",
        json=body or {},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.get_json()


class TestListShares:
    """GET /api/projects/<project>/shares/"""

    def test_list_empty(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.get(
            f"/api/projects/{pid}/shares/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_with_shares(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        make_share(client, pid, auth_headers)
        make_share(client, pid, auth_headers)
        resp = client.get(
            f"/api/projects/{pid}/shares/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_list_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.get(
            f"/api/projects/{pid}/shares/", headers=second_auth_headers
        )
        assert resp.status_code == 403


class TestCreateShare:
    """POST /api/projects/<project>/shares/"""

    def test_create_minimal(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/shares/",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["access_type"] == "view"
        assert "share_token" in data
        assert "Location" in resp.headers

    def test_create_with_options(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/shares/",
            json={
                "recipient_email": "recruiter@company.com",
                "access_type": "edit",
                "email_subject": "Check my resume",
                "email_message": "Hi there!",
                "expires_at": "2030-12-31T23:59:59",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["access_type"] == "edit"
        assert data["recipient_email"] == "recruiter@company.com"

    def test_create_invalid_access_type(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/shares/",
            json={"access_type": "admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_bad_expires_at(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/shares/",
            json={"expires_at": "not-a-datetime"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/shares/",
            json={},
            headers=second_auth_headers,
        )
        assert resp.status_code == 403


class TestPublicShareView:
    """GET /api/shares/<share_token>/"""

    def test_public_view_success(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        make_experience(app, db, pid)
        share_data = make_share(client, pid, auth_headers)
        token = share_data["share_token"]

        resp = client.get(f"/api/shares/{token}/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "project" in data
        assert "experiences" in data
        assert "share" in data

    def test_public_view_increments_view_count(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        share_data = make_share(client, pid, auth_headers)
        token = share_data["share_token"]

        client.get(f"/api/shares/{token}/")
        resp = client.get(f"/api/shares/{token}/")
        assert resp.status_code == 200

    def test_public_view_not_found(self, client):
        resp = client.get("/api/shares/nonexistenttoken123/")
        assert resp.status_code == 404

    def test_public_view_expired(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        share_data = make_share(
            client, pid, auth_headers,
            body={"expires_at": "2000-01-01T00:00:00"},
        )
        token = share_data["share_token"]
        resp = client.get(f"/api/shares/{token}/")
        assert resp.status_code == 404


class TestDeleteShare:
    """DELETE /api/shares/<share>/"""

    def test_delete_own(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        share_data = make_share(client, pid, auth_headers)
        share_id = share_data["share_id"]

        resp = client.delete(f"/api/shares/{share_id}/", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_forbidden(
        self, client, app, db, registered_user, auth_headers, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        share_data = make_share(client, pid, auth_headers)
        resp = client.delete(
            f"/api/shares/{share_data['share_id']}/",
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/shares/99999/", headers=auth_headers)
        assert resp.status_code == 404
