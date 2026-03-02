# PWP SPRING 2026
# RefOnRecord – Resume Verifier Web API
# Group information
* Student 1. Fajr Naveed   Fajr.Naveed@student.oulu.fi
* Student 2. Sillah Babar  Sillah.Babar@student.oulu.fi
* Student 3. Faisal Khan   Faisal.2.Khan@student.oulu.fi

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

## Running

```bash
flask --app resumeverifier run
```

API available at **http://localhost:5000/api/**

---

## API Endpoints

| Endpoint | Methods | Auth |
|----------|---------|------|
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

## Tests

```bash
pytest --cov=resumeverifier --cov=database --cov-report=term-missing tests/
```

## Linting

```bash
pylint resumeverifier/ database/models.py
```
