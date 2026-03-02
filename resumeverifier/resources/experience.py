"""Experience endpoints: GET/POST /api/projects/<project>/experiences/, GET/PUT/DELETE /api/experiences/<experience>/"""
from datetime import date

from flask import g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier import db, cache
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


def _exp_list_cache_key(project_id):
    return f"exp_list_{project_id}"


def _exp_cache_key(experience_id):
    return f"exp_{experience_id}"


def _parse_date(value):
    """Parse ISO date string or return None."""
    if value is None:
        return None
    return date.fromisoformat(value)


class ProjectExperienceCollection(MethodView):
    """List and create experiences within a project."""

    decorators = [require_auth]

    def get(self, project):
        """List all experiences."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache_key = _exp_list_cache_key(project.project_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), HTTP_200_OK

        experiences = [e.serialize() for e in project.experiences]
        cache.set(cache_key, experiences, timeout=_CACHE_TIMEOUT)
        return jsonify(experiences), HTTP_200_OK

    def post(self, project):
        """Add a new experience."""
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
        cache.delete(_exp_list_cache_key(project.project_id))

        response = jsonify(experience.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = f"/api/experiences/{experience.experience_id}/"
        return response


class ExperienceResource(MethodView):
    """Read, update, delete a single experience."""

    decorators = [require_auth]

    def _check_ownership(self, experience):
        if g.current_user.user_id != experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)
        return None

    def get(self, experience):
        """Get experience by ID."""
        denied = self._check_ownership(experience)
        if denied:
            return denied

        cache_key = _exp_cache_key(experience.experience_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), HTTP_200_OK

        data = experience.serialize()
        cache.set(cache_key, data, timeout=_CACHE_TIMEOUT)
        return jsonify(data), HTTP_200_OK

    def put(self, experience):
        """Update experience."""
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
        cache.delete(_exp_cache_key(experience.experience_id))
        cache.delete(_exp_list_cache_key(experience.project_id))
        return jsonify(experience.serialize()), HTTP_200_OK

    def delete(self, experience):
        """Delete experience."""
        denied = self._check_ownership(experience)
        if denied:
            return denied

        cache.delete(_exp_cache_key(experience.experience_id))
        cache.delete(_exp_list_cache_key(experience.project_id))
        db.session.delete(experience)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/projects/<project:project>/experiences/",
    view_func=ProjectExperienceCollection.as_view("project_experience_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/experiences/<experience:experience>/",
    view_func=ExperienceResource.as_view("experience_resource"),
    methods=["GET", "PUT", "DELETE"],
)
