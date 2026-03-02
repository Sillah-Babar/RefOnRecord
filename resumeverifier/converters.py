"""Custom URL converters that map integer path segments to model instances."""
from werkzeug.exceptions import NotFound
from werkzeug.routing import BaseConverter


class _IntModelConverter(BaseConverter):
    """Base converter: integer path segment → SQLAlchemy model instance."""

    model_class = None

    def to_python(self, value):
        """Fetch model by PK; raise 404 if missing."""
        from resumeverifier import db  # pylint: disable=import-outside-toplevel

        obj = db.session.get(self.model_class, int(value))
        if obj is None:
            raise NotFound(f"{self.model_class.__name__} with id={value} not found")
        return obj

    def to_url(self, value):  # pragma: no cover
        pk_col = self.model_class.__table__.primary_key.columns.values()[0].name
        return str(getattr(value, pk_col))


class UserConverter(_IntModelConverter):
    """Converts user_id to User instance."""

    def to_python(self, value):
        from resumeverifier.models import User  # pylint: disable=import-outside-toplevel
        self.model_class = User
        return super().to_python(value)

    def to_url(self, value):
        return str(value.user_id)


class ProjectConverter(_IntModelConverter):
    """Converts project_id to ResumeProject instance."""

    def to_python(self, value):
        from resumeverifier.models import ResumeProject  # pylint: disable=import-outside-toplevel
        self.model_class = ResumeProject
        return super().to_python(value)

    def to_url(self, value):
        return str(value.project_id)


class ExperienceConverter(_IntModelConverter):
    """Converts experience_id to Experience instance."""

    def to_python(self, value):
        from resumeverifier.models import Experience  # pylint: disable=import-outside-toplevel
        self.model_class = Experience
        return super().to_python(value)

    def to_url(self, value):
        return str(value.experience_id)


class VerificationRequestConverter(_IntModelConverter):
    """Converts request_id to VerificationRequest instance."""

    def to_python(self, value):
        from resumeverifier.models import VerificationRequest  # pylint: disable=import-outside-toplevel
        self.model_class = VerificationRequest
        return super().to_python(value)

    def to_url(self, value):
        return str(value.request_id)


class ShareLinkConverter(_IntModelConverter):
    """Converts share_id to ShareLink instance."""

    def to_python(self, value):
        from resumeverifier.models import ShareLink  # pylint: disable=import-outside-toplevel
        self.model_class = ShareLink
        return super().to_python(value)

    def to_url(self, value):
        return str(value.share_id)
