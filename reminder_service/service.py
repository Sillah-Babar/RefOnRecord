"""
Background Verification Reminder Service

An automated M2M microservice that:
  1. Every 15 minutes, polls the main API for pending verification requests
     older than 7 days and sends reminder emails to verifiers who haven't
     responded yet.
  2. Marks tokens that have passed their expiry date as 'expired' so the
     resume owner can re-send a fresh request.

Configuration (environment variables — share the project root .env):
  API_BASE_URL    — base URL of the main RefOnRecord API (default: http://localhost:5000)
  M2M_API_KEY     — X-API-Key value accepted by the main API
  SENDING_API_KEY — Maileroo HTTP API key (X-Sending-Key header)
  FROM_EMAIL      — verified sender address in Maileroo
  REMINDER_DB     — path to the SQLite file tracking sent reminders (default: reminders.db)
  POLL_INTERVAL   — polling interval in seconds (default: 900 = 15 min)
  REMINDER_DAYS   — days after which a reminder is sent (default: 7)

Usage:
  pip install -r requirements.txt
  python service.py
"""
import os
import sqlite3
import logging
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL    = os.environ.get("API_BASE_URL", "http://localhost:5000").rstrip("/")
M2M_API_KEY     = os.environ.get("M2M_API_KEY", "")
SENDING_API_KEY = os.environ.get("SENDING_API_KEY", "")
FROM_EMAIL      = os.environ.get("FROM_EMAIL", "noreply@46871dc7c50f7650.maileroo.org")
REMINDER_DB     = os.environ.get("REMINDER_DB", "reminders.db")
POLL_INTERVAL   = int(os.environ.get("POLL_INTERVAL", 900))
REMINDER_DAYS   = int(os.environ.get("REMINDER_DAYS", 7))

MAILEROO_SEND_URL = "https://smtp.maileroo.com/send"
M2M_HEADERS = {"X-API-Key": M2M_API_KEY}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local database — tracks which requests have already been reminded
# ---------------------------------------------------------------------------

def _get_db():
    """Return a connection to the local reminder-tracking SQLite database."""
    conn = sqlite3.connect(REMINDER_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the sent_reminders table if it does not exist."""
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_reminders (
                request_id  INTEGER PRIMARY KEY,
                reminded_at TEXT NOT NULL
            )
        """)
        conn.commit()
    log.info("Local reminder DB initialised at %s", REMINDER_DB)


def has_been_reminded(request_id):
    """Return True if a reminder email has already been sent for this request."""
    with _get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_reminders WHERE request_id = ?", (request_id,)
        ).fetchone()
    return row is not None


def record_reminder(request_id):
    """Record that a reminder was sent for the given request_id."""
    with _get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_reminders (request_id, reminded_at) VALUES (?, ?)",
            (request_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# API client helpers
# ---------------------------------------------------------------------------

def _api_get(path, params=None):
    """Perform an authenticated GET against the main API."""
    url = f"{API_BASE_URL}/api{path}"
    resp = requests.get(url, headers=M2M_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _api_patch(path, payload):
    """Perform an authenticated PATCH against the main API."""
    url = f"{API_BASE_URL}/api{path}"
    resp = requests.patch(url, headers=M2M_HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Email helper — Maileroo HTTP API
# ---------------------------------------------------------------------------

def send_reminder_email(vr):
    """
    Compose and send a verification reminder email via Maileroo HTTP API.

    ``vr`` is the full verification request dict returned by the M2M API,
    including the ``context`` block with company_name, position_title,
    requester_username, and verification_token.
    """
    ctx            = vr["context"]
    verifier_email = vr["verifier_email"]
    verifier_name  = vr["verifier_name"]
    requester      = ctx["requester_username"]
    position       = ctx["position_title"]
    company        = ctx["company_name"]
    token          = vr["verification_token"]

    verify_link = f"{API_BASE_URL}/api/verify/{token}?action=verified"
    reject_link = f"{API_BASE_URL}/api/verify/{token}?action=rejected"

    plain = (
        f"Hi {verifier_name},\n\n"
        f"This is a friendly reminder that {requester} is waiting for you to verify "
        f"their role as {position} at {company}.\n\n"
        f"You received this request {REMINDER_DAYS}+ days ago and it is still pending.\n\n"
        f"Verify:  {verify_link}\n"
        f"Reject:  {reject_link}\n\n"
        f"If you did not expect this email, please ignore it.\n\n"
        f"— RefOnRecord"
    )
    html = f"""
<p>Hi {verifier_name},</p>
<p>This is a friendly reminder that <strong>{requester}</strong> is waiting for you
to verify their role as <strong>{position}</strong> at <strong>{company}</strong>.</p>
<p>You received this request {REMINDER_DAYS}+ days ago and it is still pending.</p>
<p>
  <a href="{verify_link}" style="color:#22c55e;font-weight:bold;">Verify experience</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="{reject_link}" style="color:#ef4444;font-weight:bold;">Reject request</a>
</p>
<p><em>If you did not expect this email, please ignore it.</em></p>
<p>— RefOnRecord</p>
"""

    if not SENDING_API_KEY:
        log.info(
            "[DRY-RUN] Would send reminder to %s for request %s",
            verifier_email, vr["request_id"],
        )
        return

    payload = {
        "from": FROM_EMAIL,
        "to": verifier_email,
        "subject": f"Reminder: Please verify {requester}'s experience at {company}",
        "plain": plain,
        "html": html,
    }
    headers = {"X-API-Key": SENDING_API_KEY}

    resp = requests.post(MAILEROO_SEND_URL, data=payload, headers=headers, timeout=15)
    if resp.ok:
        log.info("Reminder email sent to %s (request_id=%s)", verifier_email, vr["request_id"])
    else:
        log.error(
            "Maileroo API error for request %s: %s %s",
            vr["request_id"], resp.status_code, resp.text,
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------

def send_reminders():
    """
    Poll the main API for pending requests older than REMINDER_DAYS days,
    skip any that have already been reminded, and send reminder emails.
    """
    log.info("Running: send_reminders (older_than=%d days)", REMINDER_DAYS)
    try:
        pending = _api_get(
            "/verification-requests/",
            params={"status": "pending", "older_than": REMINDER_DAYS},
        )
    except requests.RequestException as exc:
        log.error("Failed to fetch pending requests: %s", exc)
        return

    log.info("Found %d pending requests older than %d days", len(pending), REMINDER_DAYS)

    for vr in pending:
        rid = vr["request_id"]
        if has_been_reminded(rid):
            log.debug("Skipping request %d — already reminded", rid)
            continue
        try:
            send_reminder_email(vr)
            record_reminder(rid)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Failed to send reminder for request %d: %s", rid, exc)


def expire_stale_requests():
    """
    Poll the main API for pending requests whose token has expired,
    and mark each one as 'expired' via PATCH so the owner can re-request.
    """
    log.info("Running: expire_stale_requests")
    try:
        stale = _api_get(
            "/verification-requests/",
            params={"status": "pending", "expired": "true"},
        )
    except requests.RequestException as exc:
        log.error("Failed to fetch expired requests: %s", exc)
        return

    log.info("Found %d expired-token requests to mark", len(stale))

    for vr in stale:
        rid = vr["request_id"]
        try:
            _api_patch(f"/verification-requests/{rid}/", {"status": "expired"})
            log.info("Marked request %d as expired", rid)
        except requests.RequestException as exc:
            log.error("Failed to expire request %d: %s", rid, exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not M2M_API_KEY:
        raise SystemExit("ERROR: M2M_API_KEY environment variable is not set.")

    init_db()

    # Run once immediately on startup, then on the schedule
    send_reminders()
    expire_stale_requests()

    scheduler = BlockingScheduler()
    scheduler.add_job(send_reminders,       "interval", seconds=POLL_INTERVAL, id="reminders")
    scheduler.add_job(expire_stale_requests,"interval", seconds=POLL_INTERVAL, id="expiry")

    log.info(
        "Scheduler started — polling every %d seconds (%d min)",
        POLL_INTERVAL, POLL_INTERVAL // 60,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")
