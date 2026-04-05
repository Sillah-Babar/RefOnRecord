"""
Database Population Script for Resume Verifier API

Usage (from project root):
    python resumeverifier/populate_database.py

Prerequisites:
    Run setup_database.py first to create tables:
    python resumeverifier/setup_database.py
"""
import sys
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta

# Ensure project root is on the Python path so resumeverifier can be imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resumeverifier import create_app  # pylint: disable=wrong-import-position
from resumeverifier.extensions import db  # pylint: disable=wrong-import-position
from resumeverifier.models import (  # pylint: disable=wrong-import-position
    User, ResumeProject, Experience, VerificationRequest, ShareLink,
)


def hash_password(password):
    """Hash a password using SHA-256 (matches resumeverifier.auth.hash_password)."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token():
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def populate_database():
    """Populate the database with comprehensive sample data."""
    app = create_app()

    with app.app_context():
        print("Resume Verifier API - Database Population")

        # ====================================================================
        # 1. USERS
        # ====================================================================
        print("\nCreating users...")

        user1 = User(
            email="john.doe@email.com",
            username="johndoe",
            password_hash=hash_password("password123"),
            phone_number="+1-555-0101",
            tier="premium",
            created_at=datetime.utcnow() - timedelta(days=90),
        )
        user2 = User(
            email="jane.smith@email.com",
            username="janesmith",
            password_hash=hash_password("password456"),
            phone_number="+1-555-0102",
            tier="normal",
            created_at=datetime.utcnow() - timedelta(days=60),
        )
        user3 = User(
            email="alex.johnson@email.com",
            username="alexj",
            password_hash=hash_password("password789"),
            phone_number="+1-555-0103",
            tier="normal",
            created_at=datetime.utcnow() - timedelta(days=30),
        )

        db.session.add_all([user1, user2, user3])
        db.session.commit()
        print("  Created 3 users (1 premium, 2 normal)")

        # ====================================================================
        # 2. RESUME PROJECTS
        # ====================================================================
        print("\nCreating resume projects...")

        project1 = ResumeProject(
            user_id=user1.user_id,
            project_name="Software Engineering Resume",
            phone_number="+1-555-0101",
            linkedin_url="https://linkedin.com/in/johndoe",
            github_url="https://github.com/johndoe",
            personal_website="https://johndoe.dev",
            current_company="Tech Corp",
            is_employed=True,
            education_details=json.dumps([
                {"degree": "Bachelor of Science", "field": "Computer Science",
                 "institution": "MIT", "graduation_year": 2015, "gpa": 3.8},
                {"degree": "Master of Science", "field": "Software Engineering",
                 "institution": "Stanford University", "graduation_year": 2017, "gpa": 3.9},
            ]),
            created_at=datetime.utcnow() - timedelta(days=80),
        )
        project2 = ResumeProject(
            user_id=user1.user_id,
            project_name="Project Management Resume",
            template_style="classic",
            phone_number="+1-555-0101",
            linkedin_url="https://linkedin.com/in/johndoe",
            current_company="Tech Corp",
            is_employed=True,
            education_details=json.dumps([
                {"degree": "Bachelor of Science", "field": "Computer Science",
                 "institution": "MIT", "graduation_year": 2015, "gpa": 3.8},
            ]),
            created_at=datetime.utcnow() - timedelta(days=40),
        )
        project3 = ResumeProject(
            user_id=user2.user_id,
            project_name="Marketing Professional Resume",
            template_style="minimal",
            phone_number="+1-555-0102",
            linkedin_url="https://linkedin.com/in/janesmith",
            is_employed=False,
            education_details=json.dumps([
                {"degree": "Bachelor of Arts", "field": "Marketing",
                 "institution": "UCLA", "graduation_year": 2016, "gpa": 3.7},
            ]),
            created_at=datetime.utcnow() - timedelta(days=50),
        )
        project4 = ResumeProject(
            user_id=user3.user_id,
            project_name="Data Science Resume",
            template_style="modern",
            phone_number="+1-555-0103",
            linkedin_url="https://linkedin.com/in/alexjohnson",
            github_url="https://github.com/alexj",
            current_company="Analytics Inc",
            is_employed=True,
            education_details=json.dumps([
                {"degree": "Ph.D.", "field": "Statistics",
                 "institution": "UC Berkeley", "graduation_year": 2019, "gpa": 4.0},
            ]),
            created_at=datetime.utcnow() - timedelta(days=25),
        )

        db.session.add_all([project1, project2, project3, project4])
        db.session.commit()
        print("  Created 4 resume projects")

        # ====================================================================
        # 3. WORK EXPERIENCES
        # ====================================================================
        print("\nCreating work experiences...")

        exp1 = Experience(
            project_id=project1.project_id,
            company_name="Tech Corp",
            position_title="Senior Software Engineer",
            start_date=datetime(2020, 1, 15).date(),
            end_date=None,
            description="Leading development of microservices architecture. Mentoring junior developers.",
            verification_status="verified",
            created_at=datetime.utcnow() - timedelta(days=75),
        )
        exp2 = Experience(
            project_id=project1.project_id,
            company_name="StartupXYZ",
            position_title="Software Engineer",
            start_date=datetime(2017, 6, 1).date(),
            end_date=datetime(2019, 12, 31).date(),
            description="Developed RESTful APIs using Python and Flask. Built React front-ends.",
            verification_status="verified",
            created_at=datetime.utcnow() - timedelta(days=75),
        )
        exp3 = Experience(
            project_id=project1.project_id,
            company_name="InnovateLabs",
            position_title="Junior Developer",
            start_date=datetime(2015, 7, 1).date(),
            end_date=datetime(2017, 5, 31).date(),
            description="Built internal tools using JavaScript and Node.js.",
            verification_status="pending",
            created_at=datetime.utcnow() - timedelta(days=75),
        )
        exp4 = Experience(
            project_id=project2.project_id,
            company_name="Tech Corp",
            position_title="Technical Project Manager",
            start_date=datetime(2021, 3, 1).date(),
            end_date=None,
            description="Managing cross-functional teams of 15+ members.",
            verification_status="not_requested",
            created_at=datetime.utcnow() - timedelta(days=35),
        )
        exp5 = Experience(
            project_id=project3.project_id,
            company_name="Brand Solutions Inc",
            position_title="Senior Marketing Manager",
            start_date=datetime(2019, 1, 1).date(),
            end_date=datetime(2024, 6, 30).date(),
            description="Led marketing campaigns resulting in 40% increase in customer engagement.",
            verification_status="verified",
            created_at=datetime.utcnow() - timedelta(days=45),
        )
        exp6 = Experience(
            project_id=project3.project_id,
            company_name="Digital Marketing Agency",
            position_title="Marketing Coordinator",
            start_date=datetime(2016, 8, 1).date(),
            end_date=datetime(2018, 12, 31).date(),
            description="Coordinated social media campaigns across multiple platforms.",
            verification_status="rejected",
            created_at=datetime.utcnow() - timedelta(days=45),
        )
        exp7 = Experience(
            project_id=project4.project_id,
            company_name="Analytics Inc",
            position_title="Lead Data Scientist",
            start_date=datetime(2022, 1, 15).date(),
            end_date=None,
            description="Building ML models for customer churn prediction.",
            verification_status="verified",
            created_at=datetime.utcnow() - timedelta(days=20),
        )
        exp8 = Experience(
            project_id=project4.project_id,
            company_name="Research Institute",
            position_title="Research Scientist",
            start_date=datetime(2019, 9, 1).date(),
            end_date=datetime(2021, 12, 31).date(),
            description="Conducted statistical analysis on large datasets. Published 5 papers.",
            verification_status="pending",
            created_at=datetime.utcnow() - timedelta(days=20),
        )

        db.session.add_all([exp1, exp2, exp3, exp4, exp5, exp6, exp7, exp8])
        db.session.commit()
        print("  Created 8 work experiences")

        # ====================================================================
        # 4. VERIFICATION REQUESTS
        # ====================================================================
        print("\nCreating verification requests...")

        vr1 = VerificationRequest(
            experience_id=exp1.experience_id,
            verifier_name="Sarah Manager",
            verifier_position="Engineering Director",
            verifier_email="sarah.manager@techcorp.com",
            verification_token=generate_token(),
            status="verified",
            verifier_comment="John is an exceptional engineer.",
            requested_at=datetime.utcnow() - timedelta(days=60),
            responded_at=datetime.utcnow() - timedelta(days=55),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        vr2 = VerificationRequest(
            experience_id=exp2.experience_id,
            verifier_name="Mike Founder",
            verifier_position="CEO",
            verifier_email="mike@startupxyz.com",
            verification_token=generate_token(),
            status="verified",
            verifier_comment="John was a key member of our early engineering team.",
            requested_at=datetime.utcnow() - timedelta(days=70),
            responded_at=datetime.utcnow() - timedelta(days=65),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        vr3 = VerificationRequest(
            experience_id=exp3.experience_id,
            verifier_name="Lisa Supervisor",
            verifier_position="Senior Developer",
            verifier_email="lisa@innovatelabs.com",
            verification_token=generate_token(),
            status="pending",
            requested_at=datetime.utcnow() - timedelta(days=10),
            expires_at=datetime.utcnow() + timedelta(days=20),
        )
        vr4 = VerificationRequest(
            experience_id=exp5.experience_id,
            verifier_name="Robert Director",
            verifier_position="VP of Marketing",
            verifier_email="robert@brandsolutions.com",
            verification_token=generate_token(),
            status="verified",
            verifier_comment="Jane consistently exceeded expectations.",
            requested_at=datetime.utcnow() - timedelta(days=40),
            responded_at=datetime.utcnow() - timedelta(days=35),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        vr5 = VerificationRequest(
            experience_id=exp6.experience_id,
            verifier_name="Chris Manager",
            verifier_position="Marketing Director",
            verifier_email="chris@digitalagency.com",
            verification_token=generate_token(),
            status="rejected",
            verifier_comment="I do not recall working with Jane in this capacity.",
            requested_at=datetime.utcnow() - timedelta(days=42),
            responded_at=datetime.utcnow() - timedelta(days=38),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        vr6 = VerificationRequest(
            experience_id=exp7.experience_id,
            verifier_name="Emily CTO",
            verifier_position="Chief Technology Officer",
            verifier_email="emily.cto@analyticsinc.com",
            verification_token=generate_token(),
            status="verified",
            verifier_comment="Alex is a brilliant data scientist.",
            requested_at=datetime.utcnow() - timedelta(days=15),
            responded_at=datetime.utcnow() - timedelta(days=12),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        vr7 = VerificationRequest(
            experience_id=exp8.experience_id,
            verifier_name="Dr. Patricia Research",
            verifier_position="Principal Investigator",
            verifier_email="patricia@researchinstitute.edu",
            verification_token=generate_token(),
            status="pending",
            requested_at=datetime.utcnow() - timedelta(days=5),
            expires_at=datetime.utcnow() + timedelta(days=25),
        )
        vr8 = VerificationRequest(
            experience_id=exp3.experience_id,
            verifier_name="Tom Colleague",
            verifier_position="Developer",
            verifier_email="tom@innovatelabs.com",
            verification_token=generate_token(),
            status="pending",
            requested_at=datetime.utcnow() - timedelta(days=8),
            expires_at=datetime.utcnow() + timedelta(days=22),
        )

        db.session.add_all([vr1, vr2, vr3, vr4, vr5, vr6, vr7, vr8])
        db.session.commit()
        print("  Created 8 verification requests (4 verified, 3 pending, 1 rejected)")

        # ====================================================================
        # 5. SHARE LINKS
        # ====================================================================
        print("\nCreating share links...")

        share1 = ShareLink(
            project_id=project1.project_id,
            share_token=generate_token(),
            recipient_email="recruiter@bigtech.com",
            access_type="view",
            email_subject="My Software Engineering Resume",
            email_message="Hi! Please review my resume for the Senior Engineer position.",
            view_count=5,
            created_at=datetime.utcnow() - timedelta(days=30),
            expires_at=datetime.utcnow() + timedelta(days=60),
        )
        share2 = ShareLink(
            project_id=project1.project_id,
            share_token=generate_token(),
            recipient_email="mentor@career.com",
            access_type="edit",
            email_subject="Resume Review Request",
            email_message="Could you please review and suggest edits to my resume?",
            view_count=2,
            created_at=datetime.utcnow() - timedelta(days=20),
        )
        share3 = ShareLink(
            project_id=project2.project_id,
            share_token=generate_token(),
            recipient_email="pm.hiring@company.com",
            access_type="view",
            email_subject="Project Management Resume",
            email_message="Here is my PM-focused resume for the open position.",
            view_count=1,
            created_at=datetime.utcnow() - timedelta(days=10),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        share4 = ShareLink(
            project_id=project3.project_id,
            share_token=generate_token(),
            access_type="view",
            view_count=12,
            created_at=datetime.utcnow() - timedelta(days=45),
        )
        share5 = ShareLink(
            project_id=project4.project_id,
            share_token=generate_token(),
            recipient_email="data.recruiter@analytics.com",
            access_type="view",
            email_subject="Data Science Resume - Alex Johnson",
            email_message="Please find my resume attached via this secure link.",
            view_count=3,
            created_at=datetime.utcnow() - timedelta(days=5),
            expires_at=datetime.utcnow() + timedelta(days=45),
        )

        db.session.add_all([share1, share2, share3, share4, share5])
        db.session.commit()
        print("  Created 5 share links (4 view-only, 1 edit access)")

        print("\nDatabase population completed successfully!")


if __name__ == "__main__":
    populate_database()
