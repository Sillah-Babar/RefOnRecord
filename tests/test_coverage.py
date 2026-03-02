"""Extra tests to cover branches not hit by the main test suite."""
import smtplib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_experience, make_project, make_vr_direct


class TestEmailService:
    def test_send_no_credentials(self):
        from resumeverifier import email_service
        with patch.object(email_service, "_MAILEROO_USERNAME", ""):
            result = email_service.send_verification_email(
                "v@example.com", "Verifier", "Engineer", "Acme", "alice", "sometoken",
            )
        assert result is False

    def test_send_smtp_success(self):
        from resumeverifier import email_service
        mock_server = MagicMock()
        with patch.object(email_service, "_MAILEROO_USERNAME", "user"), \
             patch.object(email_service, "_MAILEROO_PASSWORD", "pass"), \
             patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.return_value = mock_server
            result = email_service.send_verification_email(
                "v@example.com", "Verifier", "Engineer", "Acme", "alice", "token123",
            )
        assert result is True

    def test_send_smtp_failure(self):
        from resumeverifier import email_service
        with patch.object(email_service, "_MAILEROO_USERNAME", "user"), \
             patch.object(email_service, "_MAILEROO_PASSWORD", "pass"), \
             patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.side_effect = smtplib.SMTPException("fail")
            result = email_service.send_verification_email(
                "v@example.com", "Verifier", "Engineer", "Acme", "alice", "token123",
            )
        assert result is False


class TestUserUpdateDuplicate:
    def test_update_to_existing_email(
        self, client, registered_user, second_registered_user, auth_headers
    ):
        resp = client.put(
            f"/api/users/{registered_user}/",
            json={"email": "bob@example.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 409


class TestVerificationExpiredToken:
    def test_respond_expired_token(
        self, client, app, db, registered_user, auth_headers
    ):
        _, rid, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        with app.app_context():
            from resumeverifier.models import VerificationRequest
            vr = db.session.get(VerificationRequest, rid)
            vr.expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
        resp = client.post(
            f"/api/verification-requests/{rid}/respond/",
            json={"verification_token": token, "status": "verified"},
        )
        assert resp.status_code == 400
        assert "expired" in resp.get_json()["error"].lower()


class TestVerifyByToken:
    def test_verify_confirmed(self, client, app, db, registered_user, auth_headers):
        _, _, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        resp = client.get(f"/api/verify/{token}?action=verified")
        assert resp.status_code == 200
        assert b"Verification Confirmed" in resp.data

    def test_verify_rejected(self, client, app, db, registered_user, auth_headers):
        _, _, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        resp = client.get(f"/api/verify/{token}?action=rejected")
        assert resp.status_code == 200
        assert b"Verification Rejected" in resp.data

    def test_verify_token_not_found(self, client):
        resp = client.get("/api/verify/nonexistenttoken123/")
        assert resp.status_code == 404

    def test_verify_invalid_action(self, client, app, db, registered_user, auth_headers):
        _, _, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        resp = client.get(f"/api/verify/{token}?action=maybe")
        assert resp.status_code == 400

    def test_verify_already_responded(self, client, app, db, registered_user, auth_headers):
        _, _, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        client.get(f"/api/verify/{token}?action=verified")
        resp = client.get(f"/api/verify/{token}?action=verified")
        assert resp.status_code == 400

    def test_verify_expired_token(self, client, app, db, registered_user, auth_headers):
        _, rid, token = make_vr_direct(client, app, db, registered_user, auth_headers)
        with app.app_context():
            from resumeverifier.models import VerificationRequest
            vr = db.session.get(VerificationRequest, rid)
            vr.expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
        resp = client.get(f"/api/verify/{token}?action=verified")
        assert resp.status_code == 400
