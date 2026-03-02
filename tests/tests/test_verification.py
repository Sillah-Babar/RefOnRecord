"""Tests for verification request endpoints."""
from unittest.mock import patch

from tests.conftest import make_project, make_experience


def make_vr(client, app, db, registered_user, auth_headers):
    """Helper: create a project, experience, and verification request; return IDs."""
    pid = make_project(app, db, registered_user)
    eid = make_experience(app, db, pid)
    with patch("resumeverifier.email_service.send_verification_email"):
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            json={
                "verifier_name": "Boss Man",
                "verifier_position": "Manager",
                "verifier_email": "boss@acme.com",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 201
    return eid, resp.get_json()["request_id"], resp.get_json()["verification_token"]


class TestListVerificationRequests:
    """GET /api/experiences/<experience>/verification-requests/"""

    def test_list_empty(self, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.get(
            f"/api/experiences/{eid}/verification-requests/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_with_item(self, client, app, db, registered_user, auth_headers):
        eid, _, _ = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.get(
            f"/api/experiences/{eid}/verification-requests/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_list_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.get(
            f"/api/experiences/{eid}/verification-requests/",
            headers=second_auth_headers,
        )
        assert resp.status_code == 403


class TestCreateVerificationRequest:
    """POST /api/experiences/<experience>/verification-requests/"""

    @patch("resumeverifier.email_service.send_verification_email")
    def test_create_success(self, mock_mail, client, app, db, registered_user, auth_headers):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        mock_mail.return_value = True
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            json={
                "verifier_name": "Jane Doe",
                "verifier_position": "Director",
                "verifier_email": "jane@company.com",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "pending"
        assert "verification_token" in data
        assert "Location" in resp.headers
        mock_mail.assert_called_once()

    def test_create_missing_field(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            json={"verifier_name": "X", "verifier_position": "Y"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_not_json(
        self, client, app, db, registered_user, auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            data="bad",
            content_type="text/plain",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_forbidden(
        self, client, app, db, registered_user, second_auth_headers
    ):
        pid = make_project(app, db, registered_user)
        eid = make_experience(app, db, pid)
        resp = client.post(
            f"/api/experiences/{eid}/verification-requests/",
            json={
                "verifier_name": "X",
                "verifier_position": "Y",
                "verifier_email": "x@x.com",
            },
            headers=second_auth_headers,
        )
        assert resp.status_code == 403


class TestGetVerificationRequest:
    """GET /api/verification-requests/<vr>/"""

    def test_get_own(self, client, app, db, registered_user, auth_headers):
        _, rid, _ = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.get(
            f"/api/verification-requests/{rid}/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "links" in resp.get_json()

    def test_get_forbidden(
        self, client, app, db, registered_user, auth_headers, second_auth_headers
    ):
        _, rid, _ = make_vr(client, app, db, registered_user, auth_headers)
        # Bob should not see Alice's verification request
        resp = client.get(
            f"/api/verification-requests/{rid}/", headers=second_auth_headers
        )
        assert resp.status_code == 403

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/verification-requests/99999/", headers=auth_headers)
        assert resp.status_code == 404


class TestVerificationRespond:
    """POST /api/verification-requests/<id>/respond/"""

    def test_respond_verified(self, client, app, db, registered_user, auth_headers):
        _, rid, token = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={
                "verification_token": token,
                "status": "verified",
                "verifier_comment": "Yes, confirmed.",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "verified"
        assert data["verifier_comment"] == "Yes, confirmed."

    def test_respond_rejected(self, client, app, db, registered_user, auth_headers):
        _, rid, token = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": token, "status": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "rejected"

    def test_respond_wrong_token(self, client, app, db, registered_user, auth_headers):
        _, rid, _ = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": "wrongtoken", "status": "verified"},
        )
        assert resp.status_code == 400

    def test_respond_invalid_status(
        self, client, app, db, registered_user, auth_headers
    ):
        _, rid, token = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": token, "status": "maybe"},
        )
        assert resp.status_code == 400

    def test_respond_already_responded(
        self, client, app, db, registered_user, auth_headers
    ):
        _, rid, token = make_vr(client, app, db, registered_user, auth_headers)
        client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": token, "status": "verified"},
        )
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": token, "status": "verified"},
        )
        assert resp.status_code == 400

    def test_respond_not_found(self, client):
        resp = client.post(
            "/api/verification-requests/99999/respond/",
            json={"verification_token": "x", "status": "verified"},
        )
        assert resp.status_code == 404

    def test_respond_not_json(self, client, app, db, registered_user, auth_headers):
        _, rid, _ = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            data="bad",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_respond_missing_token_field(
        self, client, app, db, registered_user, auth_headers
    ):
        _, rid, _ = make_vr(client, app, db, registered_user, auth_headers)
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"status": "verified"},
        )
        assert resp.status_code == 400
