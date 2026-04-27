"""
Tests for reminder_service/service.py
======================================
Run from the reminder_service directory:

    pytest test_service.py -v

The test suite covers:
  - Database helper functions (init, read, write)
  - Flask REST API endpoints (auth, responses, pagination)
  - Email dry-run behaviour (no SENDING_API_KEY)
  - Manual job-trigger endpoints
"""

import os
import sqlite3
import logging

import pytest

# Set required env vars BEFORE importing service so the module-level
# configuration block sees them and does not raise SystemExit.
os.environ.setdefault("M2M_API_KEY", "test-m2m-key")
os.environ.setdefault("SERVICE_API_KEY", "test-service-key")

import service  # noqa: E402  (must come after env setup above)

# ── Constants ──────────────────────────────────────────────────────────────────

_GOOD_KEY  = {"X-Service-Key": "test-service-key"}
_WRONG_KEY = {"X-Service-Key": "wrong-key"}

_SAMPLE_VR = {
    "request_id": 1,
    "verifier_email": "verifier@example.com",
    "verifier_name": "Alice Smith",
    "verification_token": "tok_abc123",
    "context": {
        "requester_username": "bob",
        "position_title": "Software Engineer",
        "company_name": "Acme Corp",
    },
}

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path):
    """
    Point service.REMINDER_DB at a fresh temporary file and initialise the
    schema.  Restores the original path after the test.
    """
    db_path = str(tmp_path / "test_reminders.db")
    original = service.REMINDER_DB
    service.REMINDER_DB = db_path
    service.init_db()
    yield db_path
    service.REMINDER_DB = original


@pytest.fixture()
def flask_client(tmp_db):
    """
    Flask test client.  Depends on tmp_db so the service uses a clean
    temporary database for every test and SERVICE_API_KEY is set to a
    known value.
    """
    original_key = service.SERVICE_API_KEY
    service.SERVICE_API_KEY = "test-service-key"
    service.app.config["TESTING"] = True
    with service.app.test_client() as c:
        yield c
    service.SERVICE_API_KEY = original_key


# ── Database helper tests ──────────────────────────────────────────────────────


class TestInitDb:
    def test_creates_sent_reminders_table(self, tmp_db):
        """init_db must create the sent_reminders table in the SQLite file."""
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='sent_reminders'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_idempotent(self, tmp_db):
        """Calling init_db a second time must not raise."""
        service.init_db()  # called once in fixture, call again here


class TestHasBeenReminded:
    def test_returns_false_for_unknown_request(self, tmp_db):
        assert service.has_been_reminded(999) is False

    def test_returns_true_after_recording(self, tmp_db):
        service.record_reminder(42)
        assert service.has_been_reminded(42) is True

    def test_does_not_leak_across_ids(self, tmp_db):
        service.record_reminder(1)
        assert service.has_been_reminded(2) is False


class TestRecordReminder:
    def test_persists_record(self, tmp_db):
        service.record_reminder(10)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT request_id FROM sent_reminders WHERE request_id = 10"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_idempotent_insert(self, tmp_db):
        """Recording the same id twice must not raise (INSERT OR IGNORE)."""
        service.record_reminder(5)
        service.record_reminder(5)
        assert service.count_reminders() == 1


class TestGetAllReminders:
    def test_empty_returns_empty_list(self, tmp_db):
        assert service.get_all_reminders() == []

    def test_returns_dicts_with_expected_keys(self, tmp_db):
        service.record_reminder(7)
        rows = service.get_all_reminders()
        assert len(rows) == 1
        assert "request_id" in rows[0]
        assert "reminded_at" in rows[0]

    def test_pagination_limit(self, tmp_db):
        for i in range(10):
            service.record_reminder(i)
        page = service.get_all_reminders(offset=0, limit=3)
        assert len(page) == 3

    def test_pagination_offset(self, tmp_db):
        for i in range(5):
            service.record_reminder(i)
        page = service.get_all_reminders(offset=4, limit=10)
        assert len(page) == 1


class TestCountReminders:
    def test_zero_when_empty(self, tmp_db):
        assert service.count_reminders() == 0

    def test_increments_on_each_record(self, tmp_db):
        service.record_reminder(1)
        service.record_reminder(2)
        assert service.count_reminders() == 2


# ── Flask endpoint tests ───────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_returns_200_without_auth(self, flask_client):
        """GET /health must not require authentication."""
        rv = flask_client.get("/health")
        assert rv.status_code == 200

    def test_body_has_status_ok(self, flask_client):
        data = flask_client.get("/health").get_json()
        assert data["status"] == "ok"

    def test_body_has_timestamp(self, flask_client):
        data = flask_client.get("/health").get_json()
        assert "timestamp" in data

    def test_body_has_links(self, flask_client):
        data = flask_client.get("/health").get_json()
        rels = [link["rel"] for link in data["links"]]
        assert "self" in rels
        assert "status" in rels


class TestAuthRequirement:
    """Every /api/* endpoint must enforce X-Service-Key authentication."""

    _PROTECTED = [
        ("GET",  "/api/status"),
        ("GET",  "/api/reminders"),
        ("POST", "/api/jobs/reminders/run"),
        ("POST", "/api/jobs/expiry/run"),
    ]

    @pytest.mark.parametrize("method,path", _PROTECTED)
    def test_missing_key_returns_401(self, flask_client, method, path):
        rv = flask_client.open(path, method=method)
        assert rv.status_code == 401

    @pytest.mark.parametrize("method,path", _PROTECTED)
    def test_wrong_key_returns_401(self, flask_client, method, path):
        rv = flask_client.open(path, method=method, headers=_WRONG_KEY)
        assert rv.status_code == 401


class TestStatusEndpoint:
    def test_returns_200_with_valid_key(self, flask_client):
        rv = flask_client.get("/api/status", headers=_GOOD_KEY)
        assert rv.status_code == 200

    def test_body_contains_scheduler_section(self, flask_client):
        data = flask_client.get("/api/status", headers=_GOOD_KEY).get_json()
        assert "scheduler" in data

    def test_body_contains_stats_section(self, flask_client):
        data = flask_client.get("/api/status", headers=_GOOD_KEY).get_json()
        assert "stats" in data
        assert "reminders" in data["stats"]
        assert "expiry" in data["stats"]

    def test_body_contains_config_section(self, flask_client):
        data = flask_client.get("/api/status", headers=_GOOD_KEY).get_json()
        assert "config" in data
        assert "api_base_url" in data["config"]

    def test_body_has_hateoas_links(self, flask_client):
        data = flask_client.get("/api/status", headers=_GOOD_KEY).get_json()
        assert isinstance(data["links"], list)
        assert len(data["links"]) > 0


class TestRemindersEndpoint:
    def test_returns_200_when_empty(self, flask_client):
        rv = flask_client.get("/api/reminders", headers=_GOOD_KEY)
        assert rv.status_code == 200

    def test_total_zero_when_empty(self, flask_client):
        data = flask_client.get("/api/reminders", headers=_GOOD_KEY).get_json()
        assert data["total"] == 0
        assert data["reminders"] == []

    def test_returns_recorded_reminders(self, flask_client, tmp_db):
        service.record_reminder(77)
        data = flask_client.get("/api/reminders", headers=_GOOD_KEY).get_json()
        assert data["total"] == 1
        assert data["reminders"][0]["request_id"] == 77

    def test_bad_offset_returns_400(self, flask_client):
        rv = flask_client.get("/api/reminders?offset=abc", headers=_GOOD_KEY)
        assert rv.status_code == 400

    def test_bad_limit_returns_400(self, flask_client):
        rv = flask_client.get("/api/reminders?limit=xyz", headers=_GOOD_KEY)
        assert rv.status_code == 400

    def test_default_pagination_fields_present(self, flask_client):
        data = flask_client.get("/api/reminders", headers=_GOOD_KEY).get_json()
        assert "offset" in data
        assert "limit" in data


class TestJobTriggerEndpoints:
    def test_trigger_reminders_returns_202(self, flask_client, monkeypatch):
        """POST /api/jobs/reminders/run must return 202 Accepted."""
        monkeypatch.setattr(service, "send_reminders", lambda: None)
        rv = flask_client.post("/api/jobs/reminders/run", headers=_GOOD_KEY)
        assert rv.status_code == 202

    def test_trigger_reminders_body(self, flask_client, monkeypatch):
        monkeypatch.setattr(service, "send_reminders", lambda: None)
        data = flask_client.post(
            "/api/jobs/reminders/run", headers=_GOOD_KEY
        ).get_json()
        assert data["job"] == "reminders"
        assert data["status"] == "triggered"

    def test_trigger_expiry_returns_202(self, flask_client, monkeypatch):
        """POST /api/jobs/expiry/run must return 202 Accepted."""
        monkeypatch.setattr(service, "expire_stale", lambda: None)
        rv = flask_client.post("/api/jobs/expiry/run", headers=_GOOD_KEY)
        assert rv.status_code == 202

    def test_trigger_expiry_body(self, flask_client, monkeypatch):
        monkeypatch.setattr(service, "expire_stale", lambda: None)
        data = flask_client.post(
            "/api/jobs/expiry/run", headers=_GOOD_KEY
        ).get_json()
        assert data["job"] == "expiry"
        assert data["status"] == "triggered"

    def test_trigger_has_hateoas_link(self, flask_client, monkeypatch):
        monkeypatch.setattr(service, "send_reminders", lambda: None)
        data = flask_client.post(
            "/api/jobs/reminders/run", headers=_GOOD_KEY
        ).get_json()
        rels = [link["rel"] for link in data["links"]]
        assert "status" in rels


# ── Email dry-run tests ────────────────────────────────────────────────────────


class TestSendReminderEmailDryRun:
    def test_no_http_call_when_sending_key_absent(self, monkeypatch, caplog):
        """
        When SENDING_API_KEY is empty the function must log a DRY-RUN message
        and return without calling requests.post.
        """
        monkeypatch.setattr(service, "SENDING_API_KEY", "")

        called = []

        def fake_post(*_args, **_kwargs):
            called.append(True)

        monkeypatch.setattr(service.requests, "post", fake_post)

        with caplog.at_level(logging.INFO):
            service.send_reminder_email(_SAMPLE_VR)

        assert "DRY-RUN" in caplog.text
        assert called == [], "requests.post must not be called in dry-run mode"
