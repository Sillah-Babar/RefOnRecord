"""Project endpoints: GET/POST /api/users/<user>/projects/, GET/PUT/DELETE /api/projects/<project>/"""
from flask import g, request, jsonify
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier import db, cache
from resumeverifier.auth import require_auth
from resumeverifier.constants import (
    PROJECT_CREATE_SCHEMA, PROJECT_UPDATE_SCHEMA,
    HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN,
    error_response,
)
from resumeverifier.models import ResumeProject
from resumeverifier.resources import api_blueprint

_CACHE_TIMEOUT = 300


def _project_cache_key(project_id):
    return f"project_{project_id}"


def _user_projects_cache_key(user_id):
    return f"user_projects_{user_id}"


class UserProjectCollection(MethodView):
    """List and create projects for a user."""

    decorators = [require_auth]

    def get(self, user):
        """List all projects."""
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache_key = _user_projects_cache_key(user.user_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), HTTP_200_OK

        projects = [p.serialize() for p in user.projects]
        cache.set(cache_key, projects, timeout=_CACHE_TIMEOUT)
        return jsonify(projects), HTTP_200_OK

    def post(self, user):
        """Create a new project."""
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, PROJECT_CREATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        project = ResumeProject(
            user_id=user.user_id,
            project_name=data["project_name"],
            template_style=data.get("template_style", "classic"),
            phone_number=data.get("phone_number"),
            linkedin_url=data.get("linkedin_url"),
            github_url=data.get("github_url"),
            personal_website=data.get("personal_website"),
            current_company=data.get("current_company"),
            is_employed=data.get("is_employed", False),
            education_details=data.get("education_details"),
        )
        db.session.add(project)
        db.session.commit()
        cache.delete(_user_projects_cache_key(user.user_id))

        response = jsonify(project.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = f"/api/projects/{project.project_id}/"
        return response


class ProjectResource(MethodView):
    """Read, update, delete a single project."""

    decorators = [require_auth]

    def get(self, project):
        """Get project by ID."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache_key = _project_cache_key(project.project_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), HTTP_200_OK

        data = project.serialize()
        cache.set(cache_key, data, timeout=_CACHE_TIMEOUT)
        return jsonify(data), HTTP_200_OK

    def put(self, project):
        """Update project."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(data, PROJECT_UPDATE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        updatable = (
            "project_name", "template_style", "phone_number", "linkedin_url",
            "github_url", "personal_website", "current_company",
            "is_employed", "education_details",
        )
        for field in updatable:
            if field in data:
                setattr(project, field, data[field])

        db.session.commit()
        cache.delete(_project_cache_key(project.project_id))
        cache.delete(_user_projects_cache_key(project.user_id))
        return jsonify(project.serialize()), HTTP_200_OK

    def delete(self, project):
        """Delete project."""
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache.delete(_project_cache_key(project.project_id))
        cache.delete(_user_projects_cache_key(project.user_id))
        db.session.delete(project)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/users/<user:user>/projects/",
    view_func=UserProjectCollection.as_view("user_project_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/projects/<project:project>/",
    view_func=ProjectResource.as_view("project_resource"),
    methods=["GET", "PUT", "DELETE"],
)
