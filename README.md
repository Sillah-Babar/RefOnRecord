# PWP SPRING 2026
# RefOnRecord – Resume Verifier Web API
# Group information
* Student 1. Fajr Naveed   Fajr.Naveed@student.oulu.fi
* Student 2. Sillah Babar  Sillah.Babar@student.oulu.fi
* Student 3. Faisal Khan   Faisal.2.Khan@student.oulu.fi

---

## Dependencies

| Library | Version | Purpose |
|---|---|---|
| Flask | 3.0.3 | Web framework and routing |
| Flask-SQLAlchemy | 3.1.1 | ORM and database management |
| Flask-Caching | 2.3.0 | Server-side response caching |
| jsonschema | 4.22.0 | JSON request body validation |
| Werkzeug | 3.0.3 | URL converters and HTTP utilities |
| python-dotenv | 1.0.1 | Loading environment variables from `.env` |
| pytest | 8.2.2 | Test runner |
| pytest-cov | 5.0.0 | Test coverage reporting |
| pylint | 3.2.3 | Static code analysis |

Install all dependencies:

```bash
pip install -r requirements.txt
```

---

## Setup

```bash
git clone <repo-url>
cd RefOnRecord
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your SMTP credentials (optional — emails are skipped if `SMTP_USERNAME` is not set).

---

## Database Setup and Population

Initialise the database schema:

```bash
python database/setup_database.py
```

Populate the database with sample data:

```bash
python database/populate_database.py
```

The application will also auto-create all tables on first run if they do not already exist.

---

## Running

```bash
flask --app resumeverifier run
```

API available at **http://localhost:5000/api/**

---

## API Endpoints

| Endpoint | Methods | Auth |
|---|---|---|
| `/api/users/` | POST | No |
| `/api/users/<user_id>/` | GET, PUT, DELETE | Bearer |
| `/api/users/<user_id>/projects/` | GET, POST | Bearer |
| `/api/projects/<project_id>/` | GET, PUT, DELETE | Bearer |
| `/api/projects/<project_id>/experiences/` | GET, POST | Bearer |
| `/api/experiences/<experience_id>/` | GET, PUT, DELETE | Bearer |
| `/api/experiences/<experience_id>/verification-requests/` | GET, POST | Bearer |
| `/api/verification-requests/<request_id>/` | GET | Bearer |
| `/api/verification-requests/<request_id>/respond/` | POST | No |
| `/api/projects/<project_id>/shares/` | GET, POST | Bearer |
| `/api/shares/<share_token>/` | GET | No |
| `/api/shares/<share_id>/` | DELETE | Bearer |
| `/api/auth/login/` | POST | No |
| `/api/auth/logout/` | DELETE | Bearer |

---

## Running the Tests

### Run the full test suite

```bash
pytest tests/
```

### Run with coverage report

```bash
pytest --cov=resumeverifier --cov=database --cov-report=term-missing tests/
```

### Run a specific test module

```bash
pytest tests/test_auth.py
pytest tests/test_user.py
pytest tests/test_project.py
pytest tests/test_experience.py
pytest tests/test_verification.py
pytest tests/test_share.py
pytest tests/test_coverage.py
```

### Run a specific test class or case

```bash
pytest tests/test_auth.py::TestLogin
pytest tests/test_auth.py::TestLogin::test_login_success
```

### Run only tests that include error/failure cases

```bash
pytest tests/ -k "forbidden or not_found or missing or invalid or duplicate or wrong or expired"
```

### Run with verbose output

```bash
pytest tests/ -v
```

Each test function is individually commented to describe what it verifies. The tests use an in-memory SQLite database (`sqlite:///:memory:`) so no external database is required.

---

## Test Suite Overview

| File | What is tested |
|---|---|
| `tests/conftest.py` | Shared fixtures: test app, clean database per test, user registration, bearer tokens, helper functions for creating projects, experiences, and verification requests |
| `tests/test_auth.py` | Login with valid credentials, wrong password, unknown email, missing field, non-JSON body, extra fields; logout success, missing token, invalid token, token invalidated after logout |
| `tests/test_user.py` | User registration with required and optional fields; duplicate email and username (409); missing required fields and short password (400); GET/PUT/DELETE with correct ownership and with a different user (403) |
| `tests/test_project.py` | List empty and populated project collections; cache consistency on repeated GET; project CRUD with valid and invalid input; ownership enforcement (403) on all methods |
| `tests/test_experience.py` | List and create experiences; date range validation (end before start returns 400); bad date format (400); GET/PUT/DELETE with ownership checks; cache hit on repeated GET; setting end_date to null |
| `tests/test_verification.py` | Create verification request and assert email is called; missing required field (400); respond with verified and rejected status; wrong token (400); already responded (400); expired token (400); 404 on unknown request ID |
| `tests/test_share.py` | Create share with minimal and full options; invalid access_type and bad expires_at (400); public access via token; expired share returns 404; view count increments; DELETE with ownership check |
| `tests/test_coverage.py` | SMTP email paths: no credentials, success, failure; duplicate email on PUT (409); expired verification token via respond endpoint; all branches of the verify-by-token HTML endpoint |

---

## Errors Detected Through Functional Testing

The following bugs were found and fixed as a direct result of running the functional test suite:

**1. Date ordering not validated on experience creation**
Tests sending `end_date` earlier than `start_date` were accepted with a 201 response. A validation check was added to the experience resource to return 400 when `end_date < start_date`.

**2. Expired verification tokens were not rejected**
Tests that manually backdated `expires_at` in the database and then submitted a respond request received a 200 instead of 400. The expiry check against `datetime.utcnow()` was missing and was added to both the respond endpoint and the `verify_by_token` function.

**3. 403 vs 404 ambiguity on cross-user access**
Requesting another user's resource was returning 404, which leaks the existence of the resource. Tests asserting 403 revealed this. Ownership checks were moved before the 404 branch so authenticated but unauthorised requests correctly return 403.

**4. Duplicate registration returned 500 instead of 409**
Tests for duplicate email and username registration revealed that the `IntegrityError` from SQLAlchemy was not caught, resulting in an unhandled 500. Specific error handling was added to return 409 with a descriptive message.

**5. Cache not invalidated after DELETE**
Tests that deleted a project and then fetched the project list still received the cached (stale) response. `cache.delete()` calls were added to all PUT and DELETE handlers to ensure the cache is cleared on mutations.

**6. Token invalidation not enforced after logout**
A test that called logout and then reused the same token expected 401 but received 200. The logout handler was confirmed to delete the session row, and the auth decorator was verified to reject tokens not present in the database.

---

## Linting

```bash
pylint resumeverifier/ database/models.py
```
