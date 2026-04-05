"""
Project endpoints:
- GET/POST /api/users/<user>/projects/ — list and create resume projects
- GET/PUT/DELETE /api/users/<user>/projects/<project>/ — read, update, delete a project

All mutating operations invalidate the relevant cache entries so subsequent
reads reflect the latest state.
"""
from flask import g, request, jsonify, url_for
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier.extensions import db, cache
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


@cache.memoize(timeout=_CACHE_TIMEOUT)
def _project_data(project_id):
    """Return serialized project data, cached by project_id."""
    project = db.session.get(ResumeProject, project_id)
    return project.serialize()


@cache.memoize(timeout=_CACHE_TIMEOUT)
def _user_projects_data(user_id):
    """Return list of serialized projects for a user, cached by user_id."""
    from resumeverifier.models import User  # pylint: disable=import-outside-toplevel
    user = db.session.get(User, user_id)
    return [p.serialize() for p in user.projects]


class UserProjectCollection(MethodView):
    """
    List and create resume projects for a specific user.

    GET returns all projects owned by the authenticated user.
    POST creates a new project and returns 201 with a Location header.
    """

    decorators = [require_auth]

    def get(self, user):
        """
        List all resume projects for the given user.

        Requires the authenticated user to be the owner.
        Results are cached by user_id.
        """
        if g.current_user.user_id != user.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        return jsonify(_user_projects_data(user.user_id)), HTTP_200_OK

    def post(self, user):
        """
        Create a new resume project for the given user.

        Validates the JSON body against PROJECT_CREATE_SCHEMA.
        Invalidates the user's project list cache on success.
        Returns 201 with a Location header pointing to the new resource.
        """
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
        cache.delete_memoized(_user_projects_data, user.user_id)

        response = jsonify(project.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = url_for("api.project_resource", user=user, project=project)
        return response


class ProjectResource(MethodView):
    """
    Read, update, and delete a single resume project.

    All operations require the authenticated user to be the project owner.
    GET results are cached by project_id.
    PUT and DELETE invalidate the project and user-level caches.
    """

    decorators = [require_auth]

    def get(self, user, project):
        """
        Retrieve a project by its ID.

        Returns cached data if available; otherwise serializes and caches.
        """
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        return jsonify(_project_data(project.project_id)), HTTP_200_OK

    def put(self, user, project):
        """
        Update one or more fields of a project.

        Validates the JSON body against PROJECT_UPDATE_SCHEMA.
        Invalidates the project-level and user-level project list caches.
        """
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
        cache.delete_memoized(_project_data, project.project_id)
        cache.delete_memoized(_user_projects_data, project.user_id)
        return jsonify(project.serialize()), HTTP_200_OK

    def delete(self, user, project):
        """
        Delete a project and all its child resources (cascade).

        Invalidates the project-level and user-level project list caches
        before deleting so stale entries are not served.
        """
        if g.current_user.user_id != project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        cache.delete_memoized(_project_data, project.project_id)
        cache.delete_memoized(_user_projects_data, project.user_id)
        db.session.delete(project)
        db.session.commit()
        return "", HTTP_204_NO_CONTENT


api_blueprint.add_url_rule(
    "/users/<user:user>/projects/",
    view_func=UserProjectCollection.as_view("user_project_collection"),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/",
    view_func=ProjectResource.as_view("project_resource"),
    methods=["GET", "PUT", "DELETE"],
)
