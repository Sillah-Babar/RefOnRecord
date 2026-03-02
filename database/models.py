"""
Resume Verifier API - Database Models

SQLAlchemy ORM models using Flask-SQLAlchemy (``db.Model``). This file is the
single source of truth for the database schema.

The ``db`` extension object is imported from ``resumeverifier.extensions`` so
that the same instance is shared with the Flask application factory.
"""
import uuid
from datetime import datetime, timedelta

from resumeverifier.extensions import db

TOKEN_EXPIRY_DAYS = 30
SESSION_EXPIRY_DAYS = 7


class User(db.Model):
    """
    Represents a registered user account.

    A user can own multiple resume projects and have multiple active sessions.
    """
    __tablename__ = "user"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    tier = db.Column(db.String(20), nullable=False, default="normal")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    projects = db.relationship(
        "ResumeProject",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    sessions = db.relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.CheckConstraint("tier IN ('normal', 'premium')", name="check_user_tier"),
        db.Index("idx_user_email", "email"),
        db.Index("idx_user_username", "username"),
    )

    def serialize(self):
        """Return a JSON-serialisable representation including HATEOAS links."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "phone_number": self.phone_number,
            "tier": self.tier,
            "created_at": self.created_at.isoformat(),
            "links": {
                "self": f"/api/users/{self.user_id}/",
                "projects": f"/api/users/{self.user_id}/projects/",
            },
        }

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}')>"


class ResumeProject(db.Model):
    """
    Represents a complete resume instance owned by a user.

    Contains template information, contact details, and employment status.
    Can have multiple work experiences and share links.
    """
    __tablename__ = "resume_project"

    project_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    project_name = db.Column(db.String(200), nullable=False)
    template_style = db.Column(db.String(50), nullable=False, default="classic")
    phone_number = db.Column(db.String(20), nullable=True)
    linkedin_url = db.Column(db.String(500), nullable=True)
    github_url = db.Column(db.String(500), nullable=True)
    personal_website = db.Column(db.String(500), nullable=True)
    current_company = db.Column(db.String(200), nullable=True)
    is_employed = db.Column(db.Boolean, nullable=False, default=False)
    education_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    owner = db.relationship("User", back_populates="projects")
    experiences = db.relationship(
        "Experience",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    share_links = db.relationship(
        "ShareLink",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.CheckConstraint(
            "template_style IN ('classic', 'modern', 'minimal')",
            name="check_template_style",
        ),
        db.Index("idx_project_user_id", "user_id"),
    )

    def serialize(self):
        """Return a JSON-serialisable representation including HATEOAS links."""
        return {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "project_name": self.project_name,
            "template_style": self.template_style,
            "phone_number": self.phone_number,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "personal_website": self.personal_website,
            "current_company": self.current_company,
            "is_employed": self.is_employed,
            "education_details": self.education_details,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "links": {
                "self": f"/api/projects/{self.project_id}/",
                "owner": f"/api/users/{self.user_id}/",
                "experiences": f"/api/projects/{self.project_id}/experiences/",
                "shares": f"/api/projects/{self.project_id}/shares/",
            },
        }

    def __repr__(self):
        return (
            f"<ResumeProject(project_id={self.project_id}, "
            f"name='{self.project_name}')>"
        )


class Experience(db.Model):
    """
    Represents a single work history entry within a resume project.

    Each experience has a verification_status that progresses from
    ``not_requested`` → ``pending`` → ``verified`` or ``rejected``.
    """
    __tablename__ = "experience"

    experience_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("resume_project.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name = db.Column(db.String(200), nullable=False)
    position_title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=False)
    verification_status = db.Column(
        db.String(20), nullable=False, default="not_requested"
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    project = db.relationship("ResumeProject", back_populates="experiences")
    verification_requests = db.relationship(
        "VerificationRequest",
        back_populates="experience",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        db.CheckConstraint(
            "verification_status IN ('not_requested', 'pending', 'verified', 'rejected')",
            name="check_verification_status",
        ),
        db.CheckConstraint(
            "(end_date IS NULL) OR (end_date >= start_date)",
            name="check_date_range",
        ),
        db.Index("idx_experience_project_id", "project_id"),
        db.Index("idx_experience_vs", "verification_status"),
    )

    def serialize(self):
        """Return a JSON-serialisable representation including HATEOAS links."""
        return {
            "experience_id": self.experience_id,
            "project_id": self.project_id,
            "company_name": self.company_name,
            "position_title": self.position_title,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "description": self.description,
            "verification_status": self.verification_status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "links": {
                "self": f"/api/experiences/{self.experience_id}/",
                "project": f"/api/projects/{self.project_id}/",
                "verification_requests": (
                    f"/api/experiences/{self.experience_id}/verification-requests/"
                ),
            },
        }

    def __repr__(self):
        return (
            f"<Experience(experience_id={self.experience_id}, "
            f"position='{self.position_title}')>"
        )


class VerificationRequest(db.Model):
    """
    Represents a pending or completed request to authenticate a work experience.

    The ``verification_token`` is a unique value sent to the verifier by email;
    it acts as the authentication credential for the respond endpoint.
    """
    __tablename__ = "verification_request"

    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    experience_id = db.Column(
        db.Integer,
        db.ForeignKey("experience.experience_id", ondelete="CASCADE"),
        nullable=False,
    )
    verifier_name = db.Column(db.String(200), nullable=False)
    verifier_position = db.Column(db.String(200), nullable=False)
    verifier_email = db.Column(db.String(255), nullable=False)
    verification_token = db.Column(db.String(255), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    verifier_comment = db.Column(db.Text, nullable=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS),
    )

    experience = db.relationship("Experience", back_populates="verification_requests")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'verified', 'rejected', 'expired')",
            name="check_request_status",
        ),
        db.Index("idx_vr_experience_id", "experience_id"),
        db.Index("idx_vr_token", "verification_token"),
        db.Index("idx_vr_status", "status"),
        db.Index("idx_vr_expires", "expires_at"),
    )

    @staticmethod
    def generate_token():
        """Generate a cryptographically random verification token."""
        return uuid.uuid4().hex

    def serialize(self):
        """Return a JSON-serialisable representation including HATEOAS links."""
        return {
            "request_id": self.request_id,
            "experience_id": self.experience_id,
            "verifier_name": self.verifier_name,
            "verifier_position": self.verifier_position,
            "verifier_email": self.verifier_email,
            "verification_token": self.verification_token,
            "status": self.status,
            "verifier_comment": self.verifier_comment,
            "requested_at": self.requested_at.isoformat(),
            "responded_at": (
                self.responded_at.isoformat() if self.responded_at else None
            ),
            "expires_at": self.expires_at.isoformat(),
            "links": {
                "self": f"/api/verification-requests/{self.request_id}/",
                "experience": f"/api/experiences/{self.experience_id}/",
                "respond": f"/api/verification-requests/{self.request_id}/respond/",
            },
        }

    def __repr__(self):
        return (
            f"<VerificationRequest(request_id={self.request_id}, "
            f"status='{self.status}')>"
        )


class ShareLink(db.Model):
    """
    Represents a secure, shareable access token for a resume project.

    Allows external viewers (recruiters, hiring managers) to access a resume
    without requiring an account. The ``share_token`` is a UUID-based string
    that provides security through obscurity.
    """
    __tablename__ = "share_link"

    share_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("resume_project.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    share_token = db.Column(db.String(255), nullable=False, unique=True)
    recipient_email = db.Column(db.String(255), nullable=True)
    access_type = db.Column(db.String(20), nullable=False, default="view")
    email_subject = db.Column(db.String(500), nullable=True)
    email_message = db.Column(db.Text, nullable=True)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("ResumeProject", back_populates="share_links")

    __table_args__ = (
        db.CheckConstraint(
            "access_type IN ('view', 'edit')", name="check_access_type"
        ),
        db.Index("idx_share_project_id", "project_id"),
        db.Index("idx_share_token", "share_token"),
    )

    @staticmethod
    def generate_token():
        """Generate a cryptographically random share token."""
        return uuid.uuid4().hex

    def serialize(self):
        """Return a JSON-serialisable representation including HATEOAS links."""
        return {
            "share_id": self.share_id,
            "project_id": self.project_id,
            "share_token": self.share_token,
            "recipient_email": self.recipient_email,
            "access_type": self.access_type,
            "email_subject": self.email_subject,
            "email_message": self.email_message,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "links": {
                "self": f"/api/shares/{self.share_token}/",
                "project": f"/api/projects/{self.project_id}/",
            },
        }

    def __repr__(self):
        return (
            f"<ShareLink(share_id={self.share_id}, "
            f"token='{self.share_token[:8]}...')>"
        )


class Session(db.Model):
    """
    Manages user authentication state.

    Each session is tied to a user account and contains a bearer token with
    an expiration timestamp. Statelessness is achieved because the server
    performs no in-memory session tracking; every request re-validates the
    token against the database.
    """
    __tablename__ = "session"

    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token = db.Column(db.String(500), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS),
    )

    user = db.relationship("User", back_populates="sessions")

    __table_args__ = (
        db.Index("idx_session_user_id", "user_id"),
        db.Index("idx_session_token", "token"),
        db.Index("idx_session_expires", "expires_at"),
    )

    @staticmethod
    def generate_token():
        """Generate a cryptographically random bearer token."""
        return str(uuid.uuid4())

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, user_id={self.user_id})>"
