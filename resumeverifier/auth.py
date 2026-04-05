"""
Authentication utilities for the Resume Verifier API.

Provides:
- ``hash_password``: SHA-256 password hashing
- ``create_token``: JWT creation for user authentication
- ``require_auth``: decorator for Bearer-token protected endpoints
- ``require_m2m_auth``: decorator for Machine-to-Machine API key protected endpoints
"""
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from resumeverifier.constants import HTTP_401_UNAUTHORIZED, error_response


def hash_password(password):
    """Return SHA-256 hex digest of password."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id):
    """
    Create a signed JWT for the given user.

    The token payload contains:
    - ``sub``: user_id (subject)
    - ``iat``: issued-at timestamp
    - ``exp``: expiry timestamp (7 days from now)

    Returns:
        tuple[str, datetime]: (token_string, expires_at_datetime)
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token, expires_at


def require_auth(view_func):
    """
    Decorator: validates Bearer JWT token and sets g.current_user.

    Extracts the Bearer token from the Authorization header, checks it
    against the cache blocklist (set on logout), then decodes and validates
    the JWT. On success, sets ``g.current_user`` and ``g.token``.
    """
    @wraps(view_func)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return error_response(
                "Missing or invalid Authorization header", HTTP_401_UNAUTHORIZED
            )

        token = auth_header[7:]

        from resumeverifier.extensions import cache  # pylint: disable=import-outside-toplevel
        if cache.get(f"blocklist:{token}"):
            return error_response("Invalid or expired token", HTTP_401_UNAUTHORIZED)

        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            return error_response("Invalid or expired token", HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return error_response("Invalid or expired token", HTTP_401_UNAUTHORIZED)

        from resumeverifier.models import User  # pylint: disable=import-outside-toplevel
        user = db_get_user(int(payload["sub"]))
        if user is None:
            return error_response("Invalid or expired token", HTTP_401_UNAUTHORIZED)

        g.current_user = user
        g.token = token
        return view_func(*args, **kwargs)

    return decorated


def db_get_user(user_id):
    """Load a User by primary key from the database."""
    from resumeverifier.extensions import db  # pylint: disable=import-outside-toplevel
    from resumeverifier.models import User  # pylint: disable=import-outside-toplevel
    return db.session.get(User, user_id)


def require_m2m_auth(view_func):
    """
    Decorator: validates Machine-to-Machine API key from X-API-Key header.

    The key must be present in ``current_app.config["M2M_API_KEYS"]`` (a set).
    Returns 401 if the header is missing or the key is not recognised.
    """
    @wraps(view_func)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key", "")
        m2m_keys = current_app.config.get("M2M_API_KEYS", set())
        if not api_key or api_key not in m2m_keys:
            return error_response("Missing or invalid API key", HTTP_401_UNAUTHORIZED)
        return view_func(*args, **kwargs)

    return decorated
