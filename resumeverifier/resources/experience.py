"""
Experience endpoints:
- GET/POST /api/users/<user>/projects/<project>/experiences/ — list and create experiences
- GET/PUT/DELETE /api/users/<user>/projects/<project>/experiences/<experience>/ — single experience

All mutating operations invalidate the relevant cache entries so subsequent
reads reflect the latest state.
"""
from datetime import date

from flask import g, request, jsonify, url_for
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier.extensions import db, cache
from resumeverifier.auth import require_auth
from resumeverifier.constants import (
    EXPERIENCE_CREATE_SCHEMA, EXPERIENCE_UPDATE_SCHEMA,
    HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN,
    error_response,
)
from resumeverifier.models import Experience
from resumeverifier.resources import api_blueprint

_CACHE_TIMEOUT = 300


@cache.memoize(timeout=_CACHE_TIMEOUT)
def _exp_data(experience_id):
    """Return serialized experience data, cached by experience_id."""
    exp = db.session.get(Experience, experience_id)
    return exp.serialize()


@cache.memoize(timeout=_CACHE_TIMEOUT)
def _exp_list_data(project_id):
    """Return list of serialized experiences for a project, cached by project_id."""
    from resumeverifier.models import ResumeProject  # pylint: disable=import-outside-toplevel
    project = db.session.get(ResumeProject, project_id)
    return [e.serialize() for e in project.experiences]


def _parse_date(value):
    """Parse ISO date string or return None."""
    if value is None:
        return None
    return date.fromisoformat(value)


class ProjectExperienceCollection(MethodView):
    """
    List and create work experiences within a resume project.

    GET returns all experiences for the project.
    POST creates a new experience, validates dates, and returns 201 with a Location header.
    """

    decorators = [require_auth]

    def get(self, user, project):
        """
        List all experiences for the given project.

        Requires the authenticated user to own the project.
        Results are cached by project_id.
        """
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        return jsonify(_exp_list_data(project.project_id)), HTTP_200_OK

    def post(self, user, project):
        """
        Add a new work experience to a project.

        Validates the JSON body against EXPERIENCE_CREATE_SCHEMA.
        Validates that end_date (if provided) is not before start_date.
        Invalidates the project's experience list cache on success.
        Returns 201 with a Location header pointing to the new resource.
        """
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, EXPERIENCE_CREATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        try:
            start = _parse_date(data["start_date"])
            end = _parse_date(data.get("end_date"))
        except ValueError as exc:  # pragma: no cover
            return error_response(str(exc), HTTP_400_BAD_REQUEST)

        if end is not None and end < start:
            return error_response("end_date must be on or after start_date", HTTP_400_BAD_REQUEST)

        experience = Experience(
            project_id=project.project_id,
            company_name=data["company_name"],
            position_title=data["position_title"],
            start_date=start,
            end_date=end,
            description=data["description"],
        )
        db.session.add(experience)
        db.session.commit()
        cache.delete_memoized(_exp_list_data, project.project_id)

        response = jsonify(experience.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = url_for(
            "api.experience_resource",
            user=project.owner,
            project=project,
            experience=experience,
        )
        return response


class ExperienceResource(MethodView):
    """
    Read, update, and delete a single work experience.

    All operations require the authenticated user to own the parent project.
    GET results are cached by experience_id.
    PUT and DELETE invalidate the experience-level and project experience-list caches.
    """

    decorators = [require_auth]

    def _check_ownership(self, experience):
        """Return an error response if the current user does not own this experience."""
        if g.current_user.user_id != experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)
        return None

    def get(self, user, project, experience):
        """
        Retrieve a work experience by its ID.

        Returns cached data if available; otherwise serializes and caches.
        """
        denied = self._check_ownership(experience)
        if denied:
            return denied

        return jsonify(_exp_data(experience.experience_id)), HTTP_200_OK

    def put(self, user, project, experience):
        """
        Update one or more fields of a work experience.

        Validates the JSON body against EXPERIENCE_UPDATE_SCHEMA.
        Validates that end_date is not before start_date after the update.
        Invalidates the experience-level and project experience-list caches.
        """
        denied = self._check_ownership(experience)
        if denied:
            return denied

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, EXPERIENCE_UPDATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        for field in ("company_name", "position_title", "description"):
            if field in data:
                setattr(experience, field, data[field])

        if "start_date" in data:
            try:
                experience.start_date = _parse_date(data["start_date"])
            except ValueError as exc:  # pragma: no cover
                return error_response(str(exc), HTTP_400_BAD_REQUEST)

        if "end_date" in data:
            try:
                experience.end_date = _parse_date(data["end_date"])
            except ValueError as exc:  # pragma: no cover
                return error_response(str(exc), HTTP_400_BAD_REQUEST)

        if experience.end_date and experience.end_date < experience.start_date:
            return error_response("end_date must be on or after start_date", HTTP_400_BAD_REQUEST)

        db.session.commit()
        cache.delete_memoized(_exp_data, experience.experience_id)
        cache.delete_memoized(_exp_list_data, experience.project_id)
        return jsonify(experience.serialize()), HTTP_200_OK

    def delete(self, user, project, experience):
        """
        Delete a work experience and all its child resources (cascade).

        Invalidates the experience-level and project experience-list caches
        before deleting so stale entries are not served.
        """
        denied = self._check_ownership(experience)
        if denied:
            return denied

        cache.delete_memoized(_exp_data, experience.experience_id)
        cache.delete_memoized(_exp_list_data, experience.project_id)
        db.session.delete(experience)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/experiences/",
    view_func=ProjectExperienceCollection.as_view("project_experience_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/experiences/<experience:experience>/",
    view_func=ExperienceResource.as_view("experience_resource"),
    methods=["GET", "PUT", "DELETE"],
)
