"""User endpoints: POST /api/users/, GET/PUT/DELETE /api/users/<user>/"""
from flask import g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker
from sqlalchemy.exc import IntegrityError

from resumeverifier import db
from resumeverifier.auth import hash_password, require_auth
from resumeverifier.constants import (
    USER_REGISTER_SCHEMA, USER_UPDATE_SCHEMA,
    HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_409_CONFLICT,
    error_response,
)
from resumeverifier.models import User
from resumeverifier.resources import api_blueprint


class UserCollection(MethodView):
    """Register a new user."""

    def post(self):
        """Create user account."""
        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, USER_REGISTER_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        user = User(
            email=data["email"],
            username=data["username"],
            password_hash=hash_password(data["password"]),
            phone_number=data.get("phone_number"),
            tier=data.get("tier", "normal"),
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return error_response("Email or username already in use", HTTP_409_CONFLICT)

        response = jsonify(user.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = f"/api/users/{user.user_id}/"
        return response


class UserResource(MethodView):
    """Read, update, delete a user (owner only)."""

    decorators = [require_auth]

    def get(self, user):
        """Get user profile."""
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)
        return jsonify(user.serialize()), HTTP_200_OK

    def put(self, user):
        """Update user profile."""
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, USER_UPDATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        for field in ("email", "username", "phone_number", "tier"):
            if field in data:
                setattr(user, field, data[field])

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return error_response("Email or username already in use", HTTP_409_CONFLICT)

        return jsonify(user.serialize()), HTTP_200_OK

    def delete(self, user):
        """Delete user account."""
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        db.session.delete(user)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/users/",
    view_func=UserCollection.as_view("user_collection"),
    methods=["POST"],
)
api_blueprint.add_url_rule(
    "/users/<user:user>/",
    view_func=UserResource.as_view("user_resource"),
    methods=["GET", "PUT", "DELETE"],
)
