"""
Share link endpoints:
- GET/POST /api/users/<user>/projects/<project>/shares/ — list and create share links
- GET /api/shares/<share_token>/ — public resume view (no auth required)
- DELETE /api/users/<user>/projects/<project>/shares/<share>/ — delete a share link

The public share view is cached by share_token. Deletions invalidate the cache.
"""
from datetime import datetime

from flask import g, request, jsonify, url_for
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier.extensions import db, cache
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


@cache.memoize(timeout=_CACHE_TIMEOUT)
def _share_public_data(share_token):
    """
    Return public share view data, cached by share_token string.

    Returns None if the share link does not exist or has expired.
    """
    share = ShareLink.query.filter_by(share_token=share_token).first()
    if share is None:
        return None
    if share.expires_at and share.expires_at < datetime.utcnow():
        return None
    project = share.project
    return {
        "project": project.serialize(),
        "experiences": [e.serialize() for e in project.experiences],
        "share": share.serialize(),
    }


class ProjectShareCollection(MethodView):
    """
    List and create share links for a resume project.

    GET returns all share links owned by the authenticated user.
    POST creates a new share link and returns 201 with a Location header.
    """

    decorators = [require_auth]

    def get(self, user, project):
        """
        List all share links for the given project.

        Requires the authenticated user to own the project.
        """
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)
        shares = [s.serialize() for s in project.share_links]
        return jsonify(shares), HTTP_200_OK

    def post(self, user, project):
        """
        Create a new share link for the given project.

        Validates the JSON body against SHARE_CREATE_SCHEMA.
        Parses the optional expires_at ISO datetime string.
        Returns 201 with a Location header pointing to the public share URL.
        """
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
        response.headers["Location"] = url_for("api.public_share", share_token=share.share_token)
        return response


class PublicShareResource(MethodView):
    """
    Public resume view — no authentication required.

    Increments the view counter and returns the serialized project, its
    experiences, and the share link metadata. Results are cached by token.
    Returns 404 if the token is unknown or the link has expired.
    """

    def get(self, share_token):
        """
        Retrieve a shared resume by its token.

        Checks the memoized cache first. On a miss, fetches from the DB,
        increments the view counter, then stores in cache.
        """
        share = ShareLink.query.filter_by(share_token=share_token).first()
        if share is None:
            return error_response("Share link not found", HTTP_404_NOT_FOUND)

        if share.expires_at and share.expires_at < datetime.utcnow():
            return error_response("Share link has expired", HTTP_404_NOT_FOUND)

        share.view_count += 1
        db.session.commit()

        # Invalidate stale memoize entry then re-fetch fresh data
        cache.delete_memoized(_share_public_data, share_token)
        data = _share_public_data(share_token)
        if data is None:
            return error_response("Share link not found", HTTP_404_NOT_FOUND)
        return jsonify(data), HTTP_200_OK


class ShareDeleteResource(MethodView):
    """
    Delete a share link (owner only).

    Invalidates the public share cache entry so stale data is not served.
    """

    decorators = [require_auth]

    def delete(self, user, project, share):
        """
        Delete the given share link.

        Requires the authenticated user to own the share link's project.
        Invalidates the memoized cache entry for the share token.
        """
        if g.current_user.user_id != share.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache.delete_memoized(_share_public_data, share.share_token)
        db.session.delete(share)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/shares/",
    view_func=ProjectShareCollection.as_view("project_share_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/shares/<share_token>/",
    view_func=PublicShareResource.as_view("public_share"),
    methods=["GET"],
)
api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/shares/<share:share>/",
    view_func=ShareDeleteResource.as_view("share_delete"),
    methods=["DELETE"],
)
