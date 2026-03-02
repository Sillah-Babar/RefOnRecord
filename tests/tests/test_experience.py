"""Tests for work experience endpoints."""
from tests.conftest import make_project, make_experience


class TestListExperiences:
    """GET /api/projects/<project>/experiences/"""

    def test_list_empty(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.get(
            f"/api/projects/{pid}/experiences/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_with_experiences(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        make_experience(app, db, pid)
        make_experience(app, db, pid)
        resp = client.get(
            f"/api/projects/{pid}/experiences/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_list_cached(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        make_experience(app, db, pid)
        r1 = client.get(f"/api/projects/{pid}/experiences/", headers=auth_headers)
        r2 = client.get(f"/api/projects/{pid}/experiences/", headers=auth_headers)
        assert r1.status_code == r2.status_code == 200

    def test_list_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.get(
            f"/api/projects/{pid}/experiences/", headers=second_auth_headers
        )
        assert resp.status_code == 403


class TestCreateExperience:
    """POST /api/projects/<project>/experiences/"""

    def _payload(self):
        return {
            "company_name": "Acme Corp",
            "position_title": "Engineer",
            "start_date": "2020-01-01",
            "description": "Built things.",
        }

    def test_create_success(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json=self._payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["company_name"] == "Acme Corp"
        assert data["verification_status"] == "not_requested"
        assert "Location" in resp.headers

    def test_create_with_end_date(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        payload = {**self._payload(), "end_date": "2022-12-31"}
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["end_date"] == "2022-12-31"

    def test_create_invalid_date_range(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        payload = {**self._payload(), "start_date": "2022-01-01", "end_date": "2021-01-01"}
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_missing_required(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json={"company_name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_not_json(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json=self._payload(),
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_create_bad_date_format(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        payload = {**self._payload(), "start_date": "not-a-date"}
        resp = client.post(
            f"/api/projects/{pid}/experiences/",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestGetExperience:
    """GET /api/experiences/<experience>/"""

    def test_get_own_experience(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.get(f"/api/experiences/{eid}/", headers=auth_headers)
        assert resp.status_code == 200
        assert "links" in resp.get_json()

    def test_get_cached(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        client.get(f"/api/experiences/{eid}/", headers=auth_headers)
        resp = client.get(f"/api/experiences/{eid}/", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.get(f"/api/experiences/{eid}/", headers=second_auth_headers)
        assert resp.status_code == 403

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/experiences/99999/", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateExperience:
    """PUT /api/experiences/<experience>/"""

    def test_update_description(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"description": "Updated description."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["description"] == "Updated description."

    def test_update_end_date_to_null(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"end_date": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["end_date"] is None

    def test_update_invalid_date_range(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"start_date": "2025-01-01", "end_date": "2020-01-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_update_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"description": "hack"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 403

    def test_update_empty(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/", json={}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_update_not_json(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_update_bad_start_date(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"start_date": "not-a-date"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_update_bad_end_date(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.put(
            f"/api/experiences/{eid}/",
            json={"end_date": "bad-date"},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestDeleteExperience:
    """DELETE /api/experiences/<experience>/"""

    def test_delete_own(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.delete(f"/api/experiences/{eid}/", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.delete(
            f"/api/experiences/{eid}/", headers=second_auth_headers
        )
        assert resp.status_code == 403
