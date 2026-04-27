# RefOnRecord — Verification Reminder Service

An autonomous M2M microservice that runs alongside the main RefOnRecord API.
It has two responsibilities:

1. **Send reminder emails** to verifiers who received a verification request
   more than `REMINDER_DAYS` days ago and have not yet responded.
2. **Expire stale tokens** by marking verification requests whose 30-day
   token window has passed as `expired`, so the resume owner can issue a
   fresh request.

Both jobs run on a configurable schedule (default: every 15 minutes).

## Why a separate service?

The main API is a stateless REST server; it should not contain scheduling
logic or maintain its own background threads.  This service communicates
with the main API exclusively through the published M2M REST interface
(`GET /api/verification-requests/` and `PATCH /api/verification-requests/{id}/`),
keeping both components independently deployable and testable.

## REST API

The service exposes its own REST API for monitoring and manual control.
All `/api/*` endpoints require the `X-Service-Key` header.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/health`                 | none           | Liveness probe |
| GET  | `/api/status`             | X-Service-Key  | Scheduler state and job stats |
| GET  | `/api/reminders`          | X-Service-Key  | List all reminders sent (paginated) |
| POST | `/api/jobs/reminders/run` | X-Service-Key  | Manually trigger reminder job |
| POST | `/api/jobs/expiry/run`    | X-Service-Key  | Manually trigger expiry job |

### API design justification

The endpoints follow REST principles: resources (`/api/reminders`) are
accessed with `GET`, and actions on job resources (`/api/jobs/reminders/run`)
use `POST`.  Responses include HATEOAS `links` arrays so clients can
discover related endpoints without hard-coding URLs.

## Communication diagram

```
┌─────────────────────┐   X-API-Key (M2M)    ┌──────────────────────┐
│  Reminder Service   │ ──────────────────── ▶│  RefOnRecord API     │
│  (this service)     │                        │  :8080               │
│                     │ ◀─────────────────────│                      │
│  - APScheduler      │   JSON responses       │  GET /api/vr/?...    │
│  - Flask REST API   │                        │  PATCH /api/vr/{id}/ │
│  - SQLite log       │                        └──────────────────────┘
└─────────────────────┘
         │  X-Service-Key
         ▼
┌─────────────────────┐
│  Admin / CI client  │  (curl, monitoring dashboard, etc.)
└─────────────────────┘
```

## Dependencies

```
requests>=2.31.0
APScheduler>=3.10.0
Flask>=3.0.0
```

## Setup

```bash
cd reminder_service
pip install -r requirements.txt
```

The service shares the root `.env` file with the main API.  Copy and
configure it:

```bash
cp ../.env.production .env
```

Required variables:

| Variable         | Description |
|------------------|-------------|
| `M2M_API_KEY`    | One of the keys in the main API's `M2M_API_KEYS` list |
| `SERVICE_API_KEY`| Key callers must send in `X-Service-Key` to use `/api/*` |
| `API_BASE_URL`   | Base URL of the main API (e.g. `http://74.241.132.64:8080`) |

Optional variables (have defaults):

| Variable          | Default | Description |
|-------------------|---------|-------------|
| `SENDING_API_KEY` | —       | Maileroo key; omit for dry-run mode |
| `FROM_EMAIL`      | noreply@... | Verified sender address |
| `REMINDER_DB`     | `reminders.db` | SQLite file path |
| `POLL_INTERVAL`   | `900`   | Scheduler interval in seconds |
| `REMINDER_DAYS`   | `7`     | Days before a reminder is sent |
| `SERVICE_PORT`    | `5001`  | Port for the Flask REST API |

## Running

```bash
export M2M_API_KEY=<key>
export SERVICE_API_KEY=<key>
export API_BASE_URL=http://74.241.132.64:8080

python service.py
```

The service will:
1. Initialise the local SQLite reminder log
2. Register and start the APScheduler background scheduler
3. Run both jobs once immediately
4. Start the Flask REST API on `SERVICE_PORT`

## Usage examples

```bash
# Liveness check
curl http://localhost:5001/health

# Check scheduler status (requires X-Service-Key)
curl -H "X-Service-Key: <key>" http://localhost:5001/api/status

# List all reminders sent
curl -H "X-Service-Key: <key>" http://localhost:5001/api/reminders

# Manually trigger reminder job
curl -X POST -H "X-Service-Key: <key>" http://localhost:5001/api/jobs/reminders/run

# Manually trigger expiry job
curl -X POST -H "X-Service-Key: <key>" http://localhost:5001/api/jobs/expiry/run
```

## Code Quality

```bash
pylint service.py --disable=C0114
```

## Files

```
reminder_service/
├── service.py       — main service: scheduler jobs + Flask API
├── requirements.txt — Python dependencies
└── README.md        — this file
```
