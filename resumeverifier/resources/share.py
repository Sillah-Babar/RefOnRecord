"""Share link endpoints: GET/POST /api/projects/<project>/shares/, GET /api/shares/<token>/, DELETE /api/shares/<share>/"""
from datetime import datetime

from flask import g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier import db, cache
from resumeverifier.auth import require_auth
from resumeverifier.constants import (
    SHARE_CREATE_SCHEMA,
    HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND,
    error_response,
)
from resumeverifier.models import ShareLink
from resumeverifier.resources import api_blueprint

_CACHE_TIMEOUT = 300


def _share_cache_key(share_token):
    return f"share_{share_token}"


class ProjectShareCollection(MethodView):
    """List and create share links for a project."""

    decorators = [require_auth]

    def get(self, project):
        """List share links."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)
        shares = [s.serialize() for s in project.share_links]
        return jsonify(shares), HTTP_200_OK

    def post(self, project):
        """Create a share link."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True) or {}

        try:
            validate(data, SHARE_CREATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        expires_at = None
        if "expires_at" in data:
            try:
                expires_at = datetime.fromisoformat(data["expires_at"])
            except ValueError as exc:
                return error_response(str(exc), HTTP_400_BAD_REQUEST)

        share = ShareLink(
            project_id=project.project_id,
            share_token=ShareLink.generate_token(),
            recipient_email=data.get("recipient_email"),
            access_type=data.get("access_type", "view"),
            email_subject=data.get("email_subject"),
            email_message=data.get("email_message"),
            expires_at=expires_at,
        )
        db.session.add(share)
        db.session.commit()

        response = jsonify(share.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = f"/api/shares/{share.share_token}/"
        return response


class PublicShareResource(MethodView):
    """Public resume view — no auth required."""

    def get(self, share_token):
        """Get shared resume by token."""
        cache_key = _share_cache_key(share_token)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), HTTP_200_OK

        share = ShareLink.query.filter_by(share_token=share_token).first()
        if share is None:
            return error_response("Share link not found", HTTP_404_NOT_FOUND)

        if share.expires_at and share.expires_at < datetime.utcnow():
            return error_response("Share link has expired", HTTP_404_NOT_FOUND)

        share.view_count += 1
        db.session.commit()

        project = share.project
        data = {
            "project": project.serialize(),
            "experiences": [e.serialize() for e in project.experiences],
            "share": share.serialize(),
        }
        cache.set(cache_key, data, timeout=_CACHE_TIMEOUT)
        return jsonify(data), HTTP_200_OK


class ShareDeleteResource(MethodView):
    """Delete a share link (owner only)."""

    decorators = [require_auth]

    def delete(self, share):
        """Delete share link."""
        if g.current_user.user_id != share.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache.delete(_share_cache_key(share.share_token))
        db.session.delete(share)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/projects/<project:project>/shares/",
    view_func=ProjectShareCollection.as_view("project_share_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/shares/<share_token>/",
    view_func=PublicShareResource.as_view("public_share"),
    methods=["GET"],
)
api_blueprint.add_url_rule(
    "/shares/<share:share>/",
    view_func=ShareDeleteResource.as_view("share_delete"),
    methods=["DELETE"],
)
