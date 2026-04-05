"""
Auth endpoints:
- POST /api/auth/login/ — authenticate and receive a JWT bearer token
- DELETE /api/auth/logout/ — invalidate the current JWT via cache blocklist
"""
from datetime import datetime, timezone

import jwt
from flask import current_app, g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier.extensions import db, cache
from resumeverifier.auth import hash_password, require_auth, create_token
from resumeverifier.constants import (
    LOGIN_SCHEMA,
    HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_204_NO_CONTENT,
    error_response,
)
from resumeverifier.models import User
from resumeverifier.resources import api_blueprint


class LoginResource(MethodView):
    """
    Handle user login and issue a JWT bearer token.

    On success returns the token string, the user_id, and the expiry datetime.
    No server-side session is stored; authentication is fully stateless.
    """

    def post(self):
        """
        Authenticate a user by email and password.

        Validates the JSON body against LOGIN_SCHEMA, then checks credentials.
        On success, creates a signed JWT via ``create_token()`` and returns it.

        Returns:
            JSON with keys ``token``, ``user_id``, ``expires_at`` on success.
            401 if credentials are invalid.
            400 if the request body is malformed.
        """
        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, LOGIN_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        user = User.query.filter_by(email=data["email"]).first()
        if user is None or user.password_hash != hash_password(data["password"]):
            return error_response("Invalid email or password", HTTP_401_UNAUTHORIZED)

        token, expires_at = create_token(user.user_id)

        return jsonify({
            "token": token,
            "user_id": user.user_id,
            "expires_at": expires_at.isoformat(),
        }), HTTP_200_OK


class LogoutResource(MethodView):
    """
    Invalidate the current JWT bearer token by adding it to the cache blocklist.

    The token is blocklisted until its natural expiry, so subsequent requests
    using it will be rejected by ``require_auth``.
    """

    decorators = [require_auth]

    def delete(self):
        """
        Blocklist the current JWT so it can no longer be used.

        Reads the token from ``g.token`` (set by ``require_auth``), decodes it
        to determine remaining TTL, then stores it in the cache blocklist with
        that timeout so the cache entry auto-expires when the JWT would anyway.

        Returns:
            Empty 204 response on success.
        """
        token = g.token
        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
            exp = payload.get("exp", 0)
            now = datetime.now(timezone.utc).timestamp()
            remaining = max(int(exp - now), 1)
        except Exception:
            remaining = 1

        cache.set(f"blocklist:{token}", True, timeout=remaining)
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/auth/login/",
    view_func=LoginResource.as_view("login"),
    methods=["POST"],
)
api_blueprint.add_url_rule(
    "/auth/logout/",
    view_func=LogoutResource.as_view("logout"),
    methods=["DELETE"],
)
