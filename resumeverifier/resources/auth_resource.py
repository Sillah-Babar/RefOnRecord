"""Auth endpoints: POST /api/auth/login/, DELETE /api/auth/logout/"""
from flask import g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier import db
from resumeverifier.auth import hash_password, require_auth
from resumeverifier.constants import (
    LOGIN_SCHEMA,
    HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_204_NO_CONTENT,
    error_response,
)
from resumeverifier.models import User, Session
from resumeverifier.resources import api_blueprint


class LoginResource(MethodView):
    """Handle login and return a bearer token."""

    def post(self):
        """Authenticate user and return token."""
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

        session = Session(user_id=user.user_id, token=Session.generate_token())
        db.session.add(session)
        db.session.commit()

        return jsonify({
            "token": session.token,
            "user_id": user.user_id,
            "expires_at": session.expires_at.isoformat(),
        }), HTTP_200_OK


class LogoutResource(MethodView):
    """Invalidate the current bearer token."""

    decorators = [require_auth]

    def delete(self):
        """Delete session."""
        token = request.headers.get("Authorization", "")[7:]
        session = Session.query.filter_by(token=token).first()
        if session:
            db.session.delete(session)
            db.session.commit()
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
