"""Bearer token auth decorator and password hashing."""
import hashlib
from datetime import datetime
from functools import wraps

from flask import g, request

from resumeverifier.constants import HTTP_401_UNAUTHORIZED, error_response


def hash_password(password):
    """Return SHA-256 hex digest of password."""
    return hashlib.sha256(password.encode()).hexdigest()


def require_auth(view_func):
    """Decorator: validates Bearer token and sets g.current_user."""
    @wraps(view_func)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return error_response(
                "Missing or invalid Authorization header", HTTP_401_UNAUTHORIZED
            )

        token = auth_header[7:]
        from resumeverifier.models import Session  # pylint: disable=import-outside-toplevel

        session = Session.query.filter_by(token=token).first()
        if session is None or session.expires_at < datetime.utcnow():
            return error_response("Invalid or expired token", HTTP_401_UNAUTHORIZED)

        g.current_user = session.user
        return view_func(*args, **kwargs)

    return decorated
