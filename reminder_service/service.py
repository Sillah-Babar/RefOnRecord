"""
RefOnRecord — Verification Reminder Service
============================================
An autonomous M2M microservice with two responsibilities:

  1. Scheduled jobs (via APScheduler BackgroundScheduler):
       • send_reminders    — every POLL_INTERVAL seconds, polls the main API
                             for pending verification requests older than
                             REMINDER_DAYS days and sends reminder emails to
                             verifiers who have not yet responded.
       • expire_stale      — marks tokens whose expiry date has passed as
                             'expired' via PATCH so the resume owner can
                             re-send a fresh request.

  2. REST API (via Flask):
       GET  /health                  — liveness probe, no auth required
       GET  /api/status              — scheduler state and job statistics
       GET  /api/reminders           — list all reminders sent (SQLite log)
       POST /api/jobs/reminders/run  — manually trigger send_reminders now
       POST /api/jobs/expiry/run     — manually trigger expire_stale now

     All /api/* endpoints require the header:
       X-Service-Key: <SERVICE_API_KEY>

Justification for a separate service
--------------------------------------
The main API is a stateless REST server whose job is to manage data integrity
and respond to HTTP requests.  Sending timed reminder emails requires a
long-running background process with its own scheduling clock and a local
database to track which reminders have already been sent.  Embedding this
in the API server would violate the single-responsibility principle, complicate
deployment, and make the API depend on a third-party email provider being
available.  A separate microservice communicates with the API using the
existing M2M authentication mechanism (X-API-Key), keeping both components
independently deployable and testable.

Configuration (environment variables)
--------------------------------------
  API_BASE_URL     — base URL of the main RefOnRecord API
                     (default: http://localhost:5000)
  M2M_API_KEY      — X-API-Key accepted by the main API
  SENDING_API_KEY  — Maileroo HTTP API key (X-Sending-Key header)
  FROM_EMAIL       — verified sender address in Maileroo
  REMINDER_DB      — path to the SQLite file for reminder tracking
                     (default: reminders.db)
  POLL_INTERVAL    — scheduler interval in seconds (default: 900)
  REMINDER_DAYS    — days after which a reminder is sent (default: 7)
  SERVICE_API_KEY  — key callers must supply in X-Service-Key header
  SERVICE_PORT     — port for the Flask REST API (default: 5001)

Usage
------
  pip install -r requirements.txt
  export M2M_API_KEY=<key> SERVICE_API_KEY=<key>
  python service.py

Sources and attribution
------------------------
All business logic in this file was written by the project team:
  - SQLite reminder-tracking helpers (_get_db, init_db, has_been_reminded,
    record_reminder, get_all_reminders, count_reminders)
  - M2M API client helpers (_api_get, _api_patch)
  - Email composition and dispatch (send_reminder_email)
  - Scheduled job implementations (send_reminders, expire_stale)
  - Flask REST API endpoints and the require_service_key auth decorator

The following third-party libraries are used without modification:
  - Flask        (BSD-3-Clause) — HTTP server and routing
  - Flask-CORS   (MIT)          — CORS headers on REST responses
  - APScheduler  (MIT)          — BackgroundScheduler for timed jobs
  - requests     (Apache-2.0)   — HTTP client for API calls and Maileroo
  - python-dotenv (BSD-3-Clause)— .env file loading

The Maileroo transactional email service is a third-party external API;
the HTTP call to it (requests.post to MAILEROO_SEND_URL) is our code, but
the underlying email delivery infrastructure belongs to Maileroo.
"""

import os
import sqlite3
import logging
import threading
import functools
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

# Load .env from the project root (one directory up from reminder_service/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuration ─────────────────────────────────────────────
API_BASE_URL     = os.environ.get("API_BASE_URL", "http://localhost:5000").rstrip("/")
M2M_API_KEY      = os.environ.get("M2M_API_KEY", "")
SENDING_API_KEY  = os.environ.get("SENDING_API_KEY", "")
FROM_EMAIL       = os.environ.get("FROM_EMAIL", "noreply@46871dc7c50f7650.maileroo.org")
REMINDER_DB      = os.environ.get("REMINDER_DB", "reminders.db")
POLL_INTERVAL    = int(os.environ.get("POLL_INTERVAL", 900))
REMINDER_DAYS    = int(os.environ.get("REMINDER_DAYS", 7))
SERVICE_API_KEY  = os.environ.get("SERVICE_API_KEY", "")
SERVICE_PORT     = int(os.environ.get("SERVICE_PORT", 5001))

MAILEROO_SEND_URL = "https://smtp.maileroo.com/send"
M2M_HEADERS       = {"X-API-Key": M2M_API_KEY}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Flask app ──────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Job statistics (thread-safe) ──────────────────────────────
_stats_lock = threading.Lock()
_stats = {
    "reminders": {
        "last_run_at":    None,
        "last_sent_count": 0,
        "total_sent":      0,
    },
    "expiry": {
        "last_run_at":      None,
        "last_expired_count": 0,
        "total_expired":      0,
    },
}

# ── APScheduler (background, runs alongside Flask) ────────────
scheduler = BackgroundScheduler()

# ── Local SQLite database ─────────────────────────────────────

def _get_db():
    """
    Open and return a connection to the local reminder-tracking SQLite database.

    The connection uses sqlite3.Row as its row_factory so that rows can be
    accessed by column name as well as by index.

    :returns: sqlite3.Connection — open connection to REMINDER_DB
    :raises sqlite3.OperationalError: if the database file path is invalid or
        the filesystem is not writable; callers should let this propagate so
        the problem is visible in logs rather than silently ignored.
    """
    conn = sqlite3.connect(REMINDER_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create the sent_reminders table if it does not already exist.

    Safe to call multiple times (CREATE TABLE IF NOT EXISTS).  Called once
    at service startup before the scheduler is started.

    Schema
    ------
      request_id  INTEGER PRIMARY KEY — verification request id from main API
      reminded_at TEXT NOT NULL       — ISO-8601 UTC timestamp of the reminder

    :returns: None
    :raises sqlite3.OperationalError: if the database file cannot be opened
        or the CREATE TABLE statement fails (e.g. disk full).  The exception
        is not caught here; it will abort startup so the operator is aware.
    """
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
    """
    Check whether a reminder email has already been sent for this request.

    Used by send_reminders() to skip requests that were handled in a
    previous scheduler run, preventing duplicate emails.

    :param request_id: int — verification request id from the main API
    :returns: bool — True if a record exists in sent_reminders, False otherwise
    :raises sqlite3.OperationalError: if the database cannot be read (e.g.
        the table was dropped or the file is corrupted).  The caller
        (send_reminders) catches broad exceptions per request, so a single
        DB failure will not abort the entire job run.
    """
    with _get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_reminders WHERE request_id = ?", (request_id,)
        ).fetchone()
    return row is not None


def record_reminder(request_id):
    """
    Persist a record that a reminder email was sent for this request.

    Uses INSERT OR IGNORE so calling this function twice with the same
    request_id is safe and idempotent — the second call is a no-op.

    :param request_id: int — verification request id from the main API
    :returns: None
    :raises sqlite3.OperationalError: if the INSERT fails due to a locked
        database or disk error.  The caller (send_reminders) catches broad
        exceptions and logs the failure without re-raising.
    """
    with _get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_reminders (request_id, reminded_at) VALUES (?, ?)",
            (request_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def get_all_reminders(offset=0, limit=50):
    """
    Return a paginated list of all reminder records from the local database.

    Results are ordered by reminded_at descending (most recent first).

    :param offset: int — number of rows to skip (default 0); negative values
        are treated as 0 by the caller before this function is invoked.
    :param limit:  int — maximum number of rows to return (default 50);
        the REST endpoint caps this at 200.
    :returns: list[dict] — each dict has keys ``request_id`` (int) and
        ``reminded_at`` (str, ISO-8601 UTC).  Empty list if no records exist.
    :raises sqlite3.OperationalError: if the database file cannot be read.
    """
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT request_id, reminded_at FROM sent_reminders "
            "ORDER BY reminded_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_reminders():
    """
    Return the total number of reminder records stored in the local database.

    Used by list_reminders() to populate the ``total`` field in paginated
    responses so callers know whether more pages exist.

    :returns: int — total row count in sent_reminders (0 if the table is empty)
    :raises sqlite3.OperationalError: if the database cannot be queried.
    """
    with _get_db() as conn:
        row = conn.execute("SELECT COUNT(*) FROM sent_reminders").fetchone()
    return row[0]

# ── API client helpers ────────────────────────────────────────

def _api_get(path, params=None):
    """
    Perform an authenticated GET request against the main RefOnRecord API.

    Attaches the M2M_API_KEY via the X-API-Key header so the main API
    recognises this service as a machine-to-machine caller.

    :param path:   str  — API path relative to /api, e.g. '/verification-requests/'
    :param params: dict | None — optional URL query parameters
    :returns: list | dict — parsed JSON body of the response
    :raises requests.HTTPError: if the server returns a 4xx or 5xx status.
        Callers should log and continue rather than crash the scheduler job.
    :raises requests.ConnectionError: if the main API is unreachable.
    :raises requests.Timeout: if the request exceeds the 10-second timeout.
    """
    url  = f"{API_BASE_URL}/api{path}"
    resp = requests.get(url, headers=M2M_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _api_patch(path, payload):
    """
    Perform an authenticated PATCH request against the main RefOnRecord API.

    Used exclusively by expire_stale() to update verification request status.

    :param path:    str  — API path relative to /api,
                           e.g. '/verification-requests/5/'
    :param payload: dict — JSON body to send (e.g. {"status": "expired"})
    :returns: dict — parsed JSON body of the response
    :raises requests.HTTPError: if the server returns a 4xx or 5xx status.
    :raises requests.ConnectionError: if the main API is unreachable.
    :raises requests.Timeout: if the request exceeds the 10-second timeout.
    """
    url  = f"{API_BASE_URL}/api{path}"
    resp = requests.patch(url, headers=M2M_HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ── Email helper ──────────────────────────────────────────────

def send_reminder_email(vr):
    """
    Compose and dispatch a verification reminder email via the Maileroo API.

    When SENDING_API_KEY is not configured the function operates in dry-run
    mode: it logs what it *would* send and returns immediately without making
    any network request.  This is useful for local development and testing.

    :param vr: dict — full verification request object as returned by the M2M
               endpoint.  Must contain the top-level keys ``request_id``,
               ``verifier_email``, ``verifier_name``, ``verification_token``,
               and a nested ``context`` dict with ``requester_username``,
               ``position_title``, and ``company_name``.
    :returns: None
    :raises KeyError: if ``vr`` is missing any of the required keys listed
        above.  The caller (send_reminders) catches broad exceptions per
        request and logs the failure.
    :raises requests.HTTPError: if Maileroo returns a non-2xx HTTP status.
        The error is logged by send_reminders and the request is skipped;
        it will be retried on the next scheduler run.
    :raises requests.ConnectionError: if the Maileroo API is unreachable.
    :raises requests.Timeout: if the POST to Maileroo exceeds 15 seconds.
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
  <a href="{verify_link}" style="color:#22c55e;font-weight:bold;">✓ Verify experience</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="{reject_link}" style="color:#ef4444;font-weight:bold;">✗ Reject request</a>
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
        "from":    FROM_EMAIL,
        "to":      verifier_email,
        "subject": f"Reminder: Please verify {requester}'s experience at {company}",
        "plain":   plain,
        "html":    html,
    }
    resp = requests.post(
        MAILEROO_SEND_URL,
        data=payload,
        headers={"X-API-Key": SENDING_API_KEY},
        timeout=15,
    )
    if resp.ok:
        log.info("Reminder sent to %s (request_id=%s)", verifier_email, vr["request_id"])
    else:
        log.error(
            "Maileroo error for request %s: %s %s",
            vr["request_id"], resp.status_code, resp.text,
        )
        resp.raise_for_status()

# ── Scheduled jobs ────────────────────────────────────────────

def send_reminders():
    """
    Scheduled job: send reminder emails for long-pending verification requests.

    Steps:
      1. Fetch all pending requests older than REMINDER_DAYS days from the
         main API using the M2M key.
      2. For each request not yet recorded in the local SQLite database,
         send a reminder email via Maileroo and record it so it is not sent again.
      3. Update the in-memory _stats dict with run timestamp and counts.

    Exceptions are handled per-request so a single failure (network error,
    bad email address, DB write failure) does not abort the entire run.
    If the initial API fetch fails the job logs the error and returns early.

    :returns: None
    :raises: does not raise — all exceptions from _api_get, send_reminder_email,
        and record_reminder are caught, logged at ERROR level, and suppressed
        so the scheduler can invoke the job again on the next interval.
    """
    log.info("Job: send_reminders (older_than=%d days)", REMINDER_DAYS)
    sent = 0
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
            sent += 1
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Failed to send reminder for request %d: %s", rid, exc)

    with _stats_lock:
        _stats["reminders"]["last_run_at"]    = datetime.now(timezone.utc).isoformat()
        _stats["reminders"]["last_sent_count"] = sent
        _stats["reminders"]["total_sent"]     += sent

    log.info("send_reminders finished — sent %d reminder(s)", sent)


def expire_stale():
    """
    Scheduled job: mark verification requests with expired tokens as 'expired'.

    Steps:
      1. Fetch all pending requests whose 30-day token window has passed
         from the main API using the M2M key (?expired=true filter).
      2. PATCH each one to status='expired' so the resume owner is unblocked
         and can send a fresh verification request.
      3. Update the in-memory _stats dict with run timestamp and counts.

    Exceptions are handled per-request so a single PATCH failure does not
    abort the processing of remaining stale requests.

    :returns: None
    :raises: does not raise — all exceptions from _api_get and _api_patch are
        caught, logged at ERROR level, and suppressed so the scheduler can
        invoke the job again on the next interval.
    """
    log.info("Job: expire_stale")
    expired_count = 0
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
            expired_count += 1
        except requests.RequestException as exc:
            log.error("Failed to expire request %d: %s", rid, exc)

    with _stats_lock:
        _stats["expiry"]["last_run_at"]        = datetime.now(timezone.utc).isoformat()
        _stats["expiry"]["last_expired_count"]  = expired_count
        _stats["expiry"]["total_expired"]      += expired_count

    log.info("expire_stale finished — expired %d request(s)", expired_count)

# ── Flask auth decorator ──────────────────────────────────────

def require_service_key(func):
    """
    Decorator that enforces X-Service-Key authentication on Flask routes.

    Wraps a Flask view function and checks the incoming X-Service-Key header
    before delegating to the view.  The wrapper preserves the original
    function's name and docstring via functools.wraps.

    :param func: callable — the Flask view function to protect
    :returns: callable — the wrapped function that performs the key check
        before calling ``func``; returns one of:
          - 503 JSON if SERVICE_API_KEY is not configured on the server
          - 401 JSON if the header is absent or does not match SERVICE_API_KEY
          - the original view's response if the key is valid
    :raises: does not raise — authentication failures are returned as HTTP
        error responses, not exceptions.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not SERVICE_API_KEY:
            return jsonify({"error": "SERVICE_API_KEY not configured on server"}), 503
        key = request.headers.get("X-Service-Key", "")
        if key != SERVICE_API_KEY:
            return jsonify({"error": "Missing or invalid X-Service-Key header"}), 401
        return func(*args, **kwargs)
    return wrapper

# ── Flask REST API endpoints ──────────────────────────────────

@app.route("/health")
def health():
    """
    Liveness probe — confirms the service process is running and reachable.

    No authentication is required so that load balancers and monitoring
    tools can poll this endpoint freely.

    :returns: 200 JSON {"status": "ok", "service": str, "timestamp": str,
        "links": list} — timestamp is ISO-8601 UTC; links include self and
        the authenticated /api/status resource.
    :raises: does not raise — any internal error would surface as a 500
        from Flask's default error handler.
    """
    return jsonify({
        "status":    "ok",
        "service":   "RefOnRecord Reminder Service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "links": [
            {"rel": "self",   "href": "/health"},
            {"rel": "status", "href": "/api/status"},
        ],
    })


@app.route("/api/status")
@require_service_key
def get_status():
    """
    Return the current scheduler state and cumulative job statistics.

    Requires a valid X-Service-Key header (enforced by require_service_key).
    The stats snapshot is taken under the _stats_lock so values are
    consistent even if a job is running concurrently.

    :returns: 200 JSON {
        "scheduler": {running, poll_interval_seconds, reminder_days, jobs},
        "stats":     {reminders: {...}, expiry: {...}},
        "config":    {api_base_url, reminder_db, dry_run},
        "links":     list of HATEOAS link objects
      }
    :raises: 401 JSON {"error": ...} — returned by require_service_key if
        the X-Service-Key header is missing or incorrect.
    :raises: 503 JSON {"error": ...} — returned by require_service_key if
        SERVICE_API_KEY is not set on the server.
    """
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        jobs.append({"id": job.id, "next_run_at": next_run})

    with _stats_lock:
        stats_snapshot = {k: dict(v) for k, v in _stats.items()}

    return jsonify({
        "scheduler": {
            "running": scheduler.running,
            "poll_interval_seconds": POLL_INTERVAL,
            "reminder_days":         REMINDER_DAYS,
            "jobs":                  jobs,
        },
        "stats": stats_snapshot,
        "config": {
            "api_base_url":   API_BASE_URL,
            "reminder_db":    REMINDER_DB,
            "dry_run":        not bool(SENDING_API_KEY),
        },
        "links": [
            {"rel": "self",              "href": "/api/status"},
            {"rel": "reminders",         "href": "/api/reminders"},
            {"rel": "run-reminders",     "href": "/api/jobs/reminders/run"},
            {"rel": "run-expiry",        "href": "/api/jobs/expiry/run"},
        ],
    })


@app.route("/api/reminders")
@require_service_key
def list_reminders():
    """
    Return a paginated list of all reminder emails that have been sent.

    Reads from the local SQLite log.  Supports the query parameters
    ``offset`` (int, default 0) and ``limit`` (int, default 50, max 200).

    :returns: 200 JSON {
        "total":     int  — total records in the database,
        "offset":    int  — the applied offset,
        "limit":     int  — the applied limit,
        "reminders": list — [{request_id, reminded_at}, ...],
        "links":     list — HATEOAS self link
      }
    :raises: 400 JSON {"error": ...} — if ``offset`` or ``limit`` cannot be
        parsed as integers.
    :raises: 401 JSON {"error": ...} — if X-Service-Key is missing or wrong.
    :raises: 503 JSON {"error": ...} — if SERVICE_API_KEY is not configured.
    """
    try:
        offset = max(0, int(request.args.get("offset", 0)))
        limit  = min(200, max(1, int(request.args.get("limit", 50))))
    except ValueError:
        return jsonify({"error": "offset and limit must be integers"}), 400

    reminders = get_all_reminders(offset=offset, limit=limit)
    total     = count_reminders()

    return jsonify({
        "total":     total,
        "offset":    offset,
        "limit":     limit,
        "reminders": reminders,
        "links": [
            {"rel": "self", "href": f"/api/reminders?offset={offset}&limit={limit}"},
        ],
    })


@app.route("/api/jobs/reminders/run", methods=["POST"])
@require_service_key
def trigger_reminders():
    """
    Immediately trigger the send_reminders job in a background thread.

    Returns 202 Accepted straight away; the job runs asynchronously.
    Use GET /api/status afterwards to see updated statistics.
    Requires a valid X-Service-Key header.

    :returns: 202 JSON {
        "job":          "reminders",
        "status":       "triggered",
        "triggered_at": str (ISO-8601 UTC),
        "links":        [{"rel": "status", "href": "/api/status"}]
      }
    :raises: 401 JSON {"error": ...} — if X-Service-Key is missing or wrong.
    :raises: 503 JSON {"error": ...} — if SERVICE_API_KEY is not configured.
    """
    thread = threading.Thread(target=send_reminders, daemon=True)
    thread.start()
    return jsonify({
        "job":       "reminders",
        "status":    "triggered",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "links": [
            {"rel": "status", "href": "/api/status"},
        ],
    }), 202


@app.route("/api/jobs/expiry/run", methods=["POST"])
@require_service_key
def trigger_expiry():
    """
    Immediately trigger the expire_stale job in a background thread.

    Returns 202 Accepted straight away; the job runs asynchronously.
    Use GET /api/status afterwards to see updated statistics.
    Requires a valid X-Service-Key header.

    :returns: 202 JSON {
        "job":          "expiry",
        "status":       "triggered",
        "triggered_at": str (ISO-8601 UTC),
        "links":        [{"rel": "status", "href": "/api/status"}]
      }
    :raises: 401 JSON {"error": ...} — if X-Service-Key is missing or wrong.
    :raises: 503 JSON {"error": ...} — if SERVICE_API_KEY is not configured.
    """
    thread = threading.Thread(target=expire_stale, daemon=True)
    thread.start()
    return jsonify({
        "job":       "expiry",
        "status":    "triggered",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "links": [
            {"rel": "status", "href": "/api/status"},
        ],
    }), 202

# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    if not M2M_API_KEY:
        raise SystemExit("ERROR: M2M_API_KEY environment variable is not set.")
    if not SERVICE_API_KEY:
        log.warning("SERVICE_API_KEY is not set — /api/* endpoints will return 503.")

    init_db()

    # Register scheduled jobs
    scheduler.add_job(send_reminders, "interval", seconds=POLL_INTERVAL, id="reminders")
    scheduler.add_job(expire_stale,   "interval", seconds=POLL_INTERVAL, id="expiry")
    scheduler.start()
    log.info("Scheduler started — polling every %d s (%d min)", POLL_INTERVAL, POLL_INTERVAL // 60)

    # Run jobs once immediately on startup
    send_reminders()
    expire_stale()

    # Start Flask (use_reloader=False prevents the scheduler starting twice
    # under Werkzeug's auto-reloader)
    log.info("Starting REST API on port %d", SERVICE_PORT)
    try:
        app.run(host="0.0.0.0", port=SERVICE_PORT, use_reloader=False)
    finally:
        scheduler.shutdown()
        log.info("Scheduler stopped.")
