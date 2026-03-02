"""
Resume Verifier API - Resources Package

Registers all resource blueprints under the ``/api`` URL prefix.
"""
from flask import Blueprint

api_blueprint = Blueprint("api", __name__, url_prefix="/api")

# Import views to register routes with the blueprint.
from resumeverifier.resources import (  # noqa: E402, F401
    auth_resource,
    user,
    project,
    experience,
    verification,
    share,
)
