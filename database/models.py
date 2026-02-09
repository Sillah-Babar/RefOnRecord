"""
Resume Verifier API - Database Models

SQLAlchemy ORM models for the Resume Verifier database.
These models match the database design specified in DATABASE_DESIGN.md
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, Date, 
    ForeignKey, CheckConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta

Base = declarative_base()


class User(Base):
    """
    Represents a registered user account.
    
    A user can own multiple resume projects and have multiple active sessions.
    """
    __tablename__ = 'user'
    
    # Primary Key
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Authentication & Contact
    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    
    # Account Information
    tier = Column(String(20), nullable=False, default='normal')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    projects = relationship(
        'ResumeProject',
        back_populates='owner',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    sessions = relationship(
        'Session',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            tier.in_(['normal', 'premium']),
            name='check_user_tier'
        ),
        Index('idx_user_email', 'email'),
        Index('idx_user_username', 'username'),
    )
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}', tier='{self.tier}')>"


class ResumeProject(Base):
    """
    Represents a complete resume instance owned by a user.
    
    Contains template information, contact details, and employment status.
    Can have multiple work experiences and share links.
    """
    __tablename__ = 'resume_project'
    
    # Primary Key
    project_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    user_id = Column(
        Integer,
        ForeignKey('user.user_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Project Information
    project_name = Column(String(200), nullable=False)
    template_style = Column(String(50), nullable=False, default='classic')
    
    # Contact & Social Media
    phone_number = Column(String(20), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    personal_website = Column(String(500), nullable=True)
    
    # Employment Status
    current_company = Column(String(200), nullable=True)
    is_employed = Column(Boolean, nullable=False, default=False)
    
    # Education (stored as JSON)
    education_details = Column(Text, nullable=True)  # JSON format
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    owner = relationship('User', back_populates='projects')
    
    experiences = relationship(
        'Experience',
        back_populates='project',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    share_links = relationship(
        'ShareLink',
        back_populates='project',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            template_style.in_(['classic', 'modern', 'minimal']),
            name='check_template_style'
        ),
        Index('idx_project_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<ResumeProject(project_id={self.project_id}, name='{self.project_name}', style='{self.template_style}')>"


class Experience(Base):
    """
    Represents a single work history entry within a resume project.
    
    Contains job details and verification status.
    Can have multiple verification requests.
    """
    __tablename__ = 'experience'
    
    # Primary Key
    experience_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    project_id = Column(
        Integer,
        ForeignKey('resume_project.project_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Work Experience Details
    company_name = Column(String(200), nullable=False)
    position_title = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL for current positions
    description = Column(Text, nullable=False)
    
    # Verification
    verification_status = Column(
        String(20),
        nullable=False,
        default='not_requested'
    )
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    project = relationship('ResumeProject', back_populates='experiences')
    
    verification_requests = relationship(
        'VerificationRequest',
        back_populates='experience',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            verification_status.in_(['not_requested', 'pending', 'verified', 'rejected']),
            name='check_verification_status'
        ),
        CheckConstraint(
            '(end_date IS NULL) OR (end_date >= start_date)',
            name='check_date_range'
        ),
        Index('idx_experience_project_id', 'project_id'),
        Index('idx_experience_verification_status', 'verification_status'),
    )
    
    def __repr__(self):
        return f"<Experience(experience_id={self.experience_id}, position='{self.position_title}', company='{self.company_name}')>"


class VerificationRequest(Base):
    """
    Represents a verification request sent to a former colleague or supervisor.
    
    Contains verifier information, secure token, and response status.
    """
    __tablename__ = 'verification_request'
    
    # Primary Key
    request_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    experience_id = Column(
        Integer,
        ForeignKey('experience.experience_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Verifier Information
    verifier_name = Column(String(200), nullable=False)
    verifier_position = Column(String(200), nullable=False)
    verifier_email = Column(String(255), nullable=False)
    
    # Verification Token & Status
    verification_token = Column(String(255), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default='pending')
    
    # Response
    verifier_comment = Column(Text, nullable=True)
    
    # Timestamps
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    expires_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=30)
    )
    
    # Relationships
    experience = relationship('Experience', back_populates='verification_requests')
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            status.in_(['pending', 'verified', 'rejected', 'expired']),
            name='check_request_status'
        ),
        Index('idx_verification_experience_id', 'experience_id'),
        Index('idx_verification_token', 'verification_token'),
        Index('idx_verification_status', 'status'),
        Index('idx_verification_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<VerificationRequest(request_id={self.request_id}, verifier='{self.verifier_name}', status='{self.status}')>"


class ShareLink(Base):
    """
    Represents a secure sharing token for a resume project.
    
    Allows external users to view resumes without authentication.
    """
    __tablename__ = 'share_link'
    
    # Primary Key
    share_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    project_id = Column(
        Integer,
        ForeignKey('resume_project.project_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Share Token & Access
    share_token = Column(String(255), nullable=False, unique=True)
    recipient_email = Column(String(255), nullable=True)
    access_type = Column(String(20), nullable=False, default='view')
    
    # Email Content (optional)
    email_subject = Column(String(500), nullable=True)
    email_message = Column(Text, nullable=True)
    
    # Analytics & Expiration
    view_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    project = relationship('ResumeProject', back_populates='share_links')
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            access_type.in_(['view', 'edit']),
            name='check_access_type'
        ),
        Index('idx_share_project_id', 'project_id'),
        Index('idx_share_token', 'share_token'),
    )
    
    def __repr__(self):
        return f"<ShareLink(share_id={self.share_id}, token='{self.share_token[:8]}...', access='{self.access_type}')>"


class Session(Base):
    """
    Represents an active authentication session for a user.
    
    Stores JWT or similar authentication token with expiration.
    """
    __tablename__ = 'session'
    
    # Primary Key
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    user_id = Column(
        Integer,
        ForeignKey('user.user_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Session Information
    token = Column(String(500), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(days=7)
    )
    
    # Relationships
    user = relationship('User', back_populates='sessions')
    
    # Constraints
    __table_args__ = (
        Index('idx_session_user_id', 'user_id'),
        Index('idx_session_token', 'token'),
        Index('idx_session_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Session(session_id={self.session_id}, user_id={self.user_id}, expires={self.expires_at})>"
    
"""
Template Table Model 

"""

class Template(Base):
    """
    Represents a resume template with its storage location.
    
    Templates are stored in S3 and referenced by resume projects.
    """
    __tablename__ = 'template'
    
    # Primary Key
    template_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Template Information
    template_name = Column(String(200), nullable=False)
    s3_path = Column(String(500), nullable=False, unique=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_template_name', 'template_name'),
        Index('idx_template_s3_path', 's3_path'),
    )
    
    def __repr__(self):
        return f"<Template(template_id={self.template_id}, name='{self.template_name}')>"
