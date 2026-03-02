"""Resume Verifier API — application factory."""
import os

from dotenv import load_dotenv
from flask import Flask

from resumeverifier.extensions import db, cache  # re-exported for convenience

load_dotenv()


def create_app(test_config=None):
    """Create and configure the Flask app."""
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(app.instance_path, "resume_verifier.db"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CACHE_TYPE="SimpleCache",
        CACHE_DEFAULT_TIMEOUT=300,
        JSON_SORT_KEYS=False,
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    cache.init_app(app)

    with app.app_context():
        from database import models  # noqa: F401
        db.create_all()

    _register_converters(app)

    from resumeverifier.resources import api_blueprint
    app.register_blueprint(api_blueprint)

    return app


def _register_converters(app):
    """Register custom URL converters."""
    from resumeverifier.converters import (  # pylint: disable=import-outside-toplevel
        UserConverter, ProjectConverter, ExperienceConverter,
        VerificationRequestConverter, ShareLinkConverter,
    )
    app.url_map.converters["user"] = UserConverter
    app.url_map.converters["project"] = ProjectConverter
    app.url_map.converters["experience"] = ExperienceConverter
    app.url_map.converters["vr"] = VerificationRequestConverter
    app.url_map.converters["share"] = ShareLinkConverter
