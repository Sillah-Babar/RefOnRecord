"""
Database Population Script for Resume Verifier API

Usage:
    python populate_database.py
    
Prerequisites:
    Run setup_database.py first to create tables
"""

import os
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, ResumeProject, Experience, VerificationRequest, ShareLink, Session
import secrets
import hashlib

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///resume_verifier.db')


def hash_password(password):
    """Simple password hashing for demonstration (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def populate_database():
    """
    Populate the database with comprehensive sample data.
    """

    print("Resume Verifier API - Database Population")

    
    # Create database engine and session
    engine = create_engine(DATABASE_URL, echo=False)
    Session_class = sessionmaker(bind=engine)
    db_session = Session_class()
    
    try:
        # ========================================
        # 1. CREATE USERS
        # ========================================
        print("Creating users...")
        
        user1 = User(
            email='john.doe@email.com',
            username='johndoe',
            password_hash=hash_password('password123'),
            phone_number='+1-555-0101',
            tier='premium',
            created_at=datetime.utcnow() - timedelta(days=90)
        )
        
        user2 = User(
            email='jane.smith@email.com',
            username='janesmith',
            password_hash=hash_password('password456'),
            phone_number='+1-555-0102',
            tier='normal',
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        
        user3 = User(
            email='alex.johnson@email.com',
            username='alexj',
            password_hash=hash_password('password789'),
            phone_number='+1-555-0103',
            tier='normal',
            created_at=datetime.utcnow() - timedelta(days=30)
        )
        
        db_session.add_all([user1, user2, user3])
        db_session.commit()
        print(f"reated 3 users (1 premium, 2 normal)")
        
        # ========================================
        # 2. CREATE RESUME PROJECTS
        # ========================================
        print("\nCreating resume projects...")
        
        # User 1's projects (Premium user - 2 projects)
        project1 = ResumeProject(
            user_id=user1.user_id,
            project_name='Software Engineering Resume',
            phone_number='+1-555-0101',
            linkedin_url='https://linkedin.com/in/johndoe',
            github_url='https://github.com/johndoe',
            personal_website='https://johndoe.dev',
            current_company='Tech Corp',
            is_employed=True,
            education_details=json.dumps([
                {
                    'degree': 'Bachelor of Science',
                    'field': 'Computer Science',
                    'institution': 'MIT',
                    'graduation_year': 2015,
                    'gpa': 3.8
                },
                {
                    'degree': 'Master of Science',
                    'field': 'Software Engineering',
                    'institution': 'Stanford University',
                    'graduation_year': 2017,
                    'gpa': 3.9
                }
            ]),
            created_at=datetime.utcnow() - timedelta(days=80)
        )
        
        project2 = ResumeProject(
            user_id=user1.user_id,
            project_name='Project Management Resume',
            template_style='classic',
            phone_number='+1-555-0101',
            linkedin_url='https://linkedin.com/in/johndoe',
            current_company='Tech Corp',
            is_employed=True,
            education_details=json.dumps([
                {
                    'degree': 'Bachelor of Science',
                    'field': 'Computer Science',
                    'institution': 'MIT',
                    'graduation_year': 2015,
                    'gpa': 3.8
                }
            ]),
            created_at=datetime.utcnow() - timedelta(days=40)
        )
        
        # User 2's project
        project3 = ResumeProject(
            user_id=user2.user_id,
            project_name='Marketing Professional Resume',
            template_style='minimal',
            phone_number='+1-555-0102',
            linkedin_url='https://linkedin.com/in/janesmith',
            current_company=None,
            is_employed=False,
            education_details=json.dumps([
                {
                    'degree': 'Bachelor of Arts',
                    'field': 'Marketing',
                    'institution': 'UCLA',
                    'graduation_year': 2016,
                    'gpa': 3.7
                }
            ]),
            created_at=datetime.utcnow() - timedelta(days=50)
        )
        
        # User 3's project
        project4 = ResumeProject(
            user_id=user3.user_id,
            project_name='Data Science Resume',
            template_style='modern',
            phone_number='+1-555-0103',
            linkedin_url='https://linkedin.com/in/alexjohnson',
            github_url='https://github.com/alexj',
            current_company='Analytics Inc',
            is_employed=True,
            education_details=json.dumps([
                {
                    'degree': 'Ph.D.',
                    'field': 'Statistics',
                    'institution': 'UC Berkeley',
                    'graduation_year': 2019,
                    'gpa': 4.0
                }
            ]),
            created_at=datetime.utcnow() - timedelta(days=25)
        )
        
        db_session.add_all([project1, project2, project3, project4])
        db_session.commit()
        print(f"Created 4 resume projects")
        
        # ========================================
        # 3. CREATE WORK EXPERIENCES
        # ========================================
        print("\nCreating work experiences...")
        
        # Project 1 experiences (Software Engineering)
        exp1 = Experience(
            project_id=project1.project_id,
            company_name='Tech Corp',
            position_title='Senior Software Engineer',
            start_date=datetime(2020, 1, 15).date(),
            end_date=None,  # Current position
            description='Leading development of microservices architecture. Mentoring junior developers. Implementing CI/CD pipelines and improving code quality through comprehensive testing.',
            verification_status='verified',
            created_at=datetime.utcnow() - timedelta(days=75)
        )
        
        exp2 = Experience(
            project_id=project1.project_id,
            company_name='StartupXYZ',
            position_title='Software Engineer',
            start_date=datetime(2017, 6, 1).date(),
            end_date=datetime(2019, 12, 31).date(),
            description='Developed RESTful APIs using Python and Flask. Built responsive front-end interfaces with React. Collaborated with cross-functional teams to deliver features.',
            verification_status='verified',
            created_at=datetime.utcnow() - timedelta(days=75)
        )
        
        exp3 = Experience(
            project_id=project1.project_id,
            company_name='InnovateLabs',
            position_title='Junior Developer',
            start_date=datetime(2015, 7, 1).date(),
            end_date=datetime(2017, 5, 31).date(),
            description='Built internal tools using JavaScript and Node.js. Participated in agile development cycles. Fixed bugs and improved application performance.',
            verification_status='pending',
            created_at=datetime.utcnow() - timedelta(days=75)
        )
        
        # Project 2 experiences (Project Management)
        exp4 = Experience(
            project_id=project2.project_id,
            company_name='Tech Corp',
            position_title='Technical Project Manager',
            start_date=datetime(2021, 3, 1).date(),
            end_date=None,
            description='Managing cross-functional teams of 15+ members. Overseeing product roadmap and sprint planning. Stakeholder communication and risk management.',
            verification_status='not_requested',
            created_at=datetime.utcnow() - timedelta(days=35)
        )
        
        # Project 3 experiences (Marketing)
        exp5 = Experience(
            project_id=project3.project_id,
            company_name='Brand Solutions Inc',
            position_title='Senior Marketing Manager',
            start_date=datetime(2019, 1, 1).date(),
            end_date=datetime(2024, 6, 30).date(),
            description='Led marketing campaigns resulting in 40% increase in customer engagement. Managed budget of $500K. Coordinated with design and content teams.',
            verification_status='verified',
            created_at=datetime.utcnow() - timedelta(days=45)
        )
        
        exp6 = Experience(
            project_id=project3.project_id,
            company_name='Digital Marketing Agency',
            position_title='Marketing Coordinator',
            start_date=datetime(2016, 8, 1).date(),
            end_date=datetime(2018, 12, 31).date(),
            description='Coordinated social media campaigns across multiple platforms. Analyzed campaign metrics and prepared reports. Collaborated with clients on strategy.',
            verification_status='rejected',
            created_at=datetime.utcnow() - timedelta(days=45)
        )
        
        # Project 4 experiences (Data Science)
        exp7 = Experience(
            project_id=project4.project_id,
            company_name='Analytics Inc',
            position_title='Lead Data Scientist',
            start_date=datetime(2022, 1, 15).date(),
            end_date=None,
            description='Building machine learning models for customer churn prediction. Leading a team of 5 data scientists. Presenting insights to C-level executives.',
            verification_status='verified',
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        
        exp8 = Experience(
            project_id=project4.project_id,
            company_name='Research Institute',
            position_title='Research Scientist',
            start_date=datetime(2019, 9, 1).date(),
            end_date=datetime(2021, 12, 31).date(),
            description='Conducted statistical analysis on large datasets. Published 5 peer-reviewed papers. Developed novel algorithms for data processing.',
            verification_status='pending',
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        
        db_session.add_all([exp1, exp2, exp3, exp4, exp5, exp6, exp7, exp8])
        db_session.commit()
        print(f"  ✓ Created 8 work experiences")
        
        # ========================================
        # 4. CREATE VERIFICATION REQUESTS
        # ========================================
        print("\nCreating verification requests...")
        
        # Verified request for exp1
        vr1 = VerificationRequest(
            experience_id=exp1.experience_id,
            verifier_name='Sarah Manager',
            verifier_position='Engineering Director',
            verifier_email='sarah.manager@techcorp.com',
            verification_token=generate_token(),
            status='verified',
            verifier_comment='John is an exceptional engineer. His technical skills and leadership have been invaluable to our team.',
            requested_at=datetime.utcnow() - timedelta(days=60),
            responded_at=datetime.utcnow() - timedelta(days=55),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Verified request for exp2
        vr2 = VerificationRequest(
            experience_id=exp2.experience_id,
            verifier_name='Mike Founder',
            verifier_position='CEO',
            verifier_email='mike@startupxyz.com',
            verification_token=generate_token(),
            status='verified',
            verifier_comment='John was a key member of our early engineering team. Highly recommend!',
            requested_at=datetime.utcnow() - timedelta(days=70),
            responded_at=datetime.utcnow() - timedelta(days=65),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Pending request for exp3
        vr3 = VerificationRequest(
            experience_id=exp3.experience_id,
            verifier_name='Lisa Supervisor',
            verifier_position='Senior Developer',
            verifier_email='lisa@innovatelabs.com',
            verification_token=generate_token(),
            status='pending',
            verifier_comment=None,
            requested_at=datetime.utcnow() - timedelta(days=10),
            responded_at=None,
            expires_at=datetime.utcnow() + timedelta(days=20)
        )
        
        # Verified request for exp5
        vr4 = VerificationRequest(
            experience_id=exp5.experience_id,
            verifier_name='Robert Director',
            verifier_position='VP of Marketing',
            verifier_email='robert@brandsolutions.com',
            verification_token=generate_token(),
            status='verified',
            verifier_comment='Jane consistently exceeded expectations. Her campaigns drove significant business growth.',
            requested_at=datetime.utcnow() - timedelta(days=40),
            responded_at=datetime.utcnow() - timedelta(days=35),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Rejected request for exp6
        vr5 = VerificationRequest(
            experience_id=exp6.experience_id,
            verifier_name='Chris Manager',
            verifier_position='Marketing Director',
            verifier_email='chris@digitalagency.com',
            verification_token=generate_token(),
            status='rejected',
            verifier_comment='I do not recall working with Jane in this capacity during the stated time period.',
            requested_at=datetime.utcnow() - timedelta(days=42),
            responded_at=datetime.utcnow() - timedelta(days=38),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Verified request for exp7
        vr6 = VerificationRequest(
            experience_id=exp7.experience_id,
            verifier_name='Emily CTO',
            verifier_position='Chief Technology Officer',
            verifier_email='emily.cto@analyticsinc.com',
            verification_token=generate_token(),
            status='verified',
            verifier_comment='Alex is a brilliant data scientist. Their models have saved us millions in operational costs.',
            requested_at=datetime.utcnow() - timedelta(days=15),
            responded_at=datetime.utcnow() - timedelta(days=12),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Pending request for exp8
        vr7 = VerificationRequest(
            experience_id=exp8.experience_id,
            verifier_name='Dr. Patricia Research',
            verifier_position='Principal Investigator',
            verifier_email='patricia@researchinstitute.edu',
            verification_token=generate_token(),
            status='pending',
            verifier_comment=None,
            requested_at=datetime.utcnow() - timedelta(days=5),
            responded_at=None,
            expires_at=datetime.utcnow() + timedelta(days=25)
        )
        
        # Additional pending request for exp3 (multiple verifiers)
        vr8 = VerificationRequest(
            experience_id=exp3.experience_id,
            verifier_name='Tom Colleague',
            verifier_position='Developer',
            verifier_email='tom@innovatelabs.com',
            verification_token=generate_token(),
            status='pending',
            verifier_comment=None,
            requested_at=datetime.utcnow() - timedelta(days=8),
            responded_at=None,
            expires_at=datetime.utcnow() + timedelta(days=22)
        )
        
        db_session.add_all([vr1, vr2, vr3, vr4, vr5, vr6, vr7, vr8])
        db_session.commit()
        print(f"Created 8 verification requests (4 verified, 3 pending, 1 rejected)")
        
        # ========================================
        # 5. CREATE SHARE LINKS
        # ========================================
        print("\nCreating share links...")
        
        # Share link for project1 (view-only)
        share1 = ShareLink(
            project_id=project1.project_id,
            share_token=generate_token(),
            recipient_email='recruiter@bigtech.com',
            access_type='view',
            email_subject='My Software Engineering Resume',
            email_message='Hi! Please review my resume for the Senior Engineer position.',
            view_count=5,
            created_at=datetime.utcnow() - timedelta(days=30),
            expires_at=datetime.utcnow() + timedelta(days=60)
        )
        
        # Share link for project1 (edit access - premium feature)
        share2 = ShareLink(
            project_id=project1.project_id,
            share_token=generate_token(),
            recipient_email='mentor@career.com',
            access_type='edit',
            email_subject='Resume Review Request',
            email_message='Could you please review and suggest edits to my resume?',
            view_count=2,
            created_at=datetime.utcnow() - timedelta(days=20),
            expires_at=None  # No expiration
        )
        
        # Share link for project2 (view-only)
        share3 = ShareLink(
            project_id=project2.project_id,
            share_token=generate_token(),
            recipient_email='pm.hiring@company.com',
            access_type='view',
            email_subject='Project Management Resume',
            email_message='Here is my PM-focused resume for the open position.',
            view_count=1,
            created_at=datetime.utcnow() - timedelta(days=10),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Share link for project3 (view-only, no recipient)
        share4 = ShareLink(
            project_id=project3.project_id,
            share_token=generate_token(),
            recipient_email=None,
            access_type='view',
            email_subject=None,
            email_message=None,
            view_count=12,  # Public link, more views
            created_at=datetime.utcnow() - timedelta(days=45),
            expires_at=None
        )
        
        # Share link for project4 (view-only)
        share5 = ShareLink(
            project_id=project4.project_id,
            share_token=generate_token(),
            recipient_email='data.recruiter@analytics.com',
            access_type='view',
            email_subject='Data Science Resume - Alex Johnson',
            email_message='Please find my resume attached via this secure link.',
            view_count=3,
            created_at=datetime.utcnow() - timedelta(days=5),
            expires_at=datetime.utcnow() + timedelta(days=45)
        )
        
        db_session.add_all([share1, share2, share3, share4, share5])
        db_session.commit()
        print(f"Created 5 share links (4 view-only, 1 edit access)")
        
        # ========================================
        # 6. CREATE SESSIONS
        # ========================================
        print("\nCreating active sessions...")
        
        # User 1 sessions (multiple devices)
        session1 = Session(
            user_id=user1.user_id,
            token=generate_token(),
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        session2 = Session(
            user_id=user1.user_id,
            token=generate_token(),
            created_at=datetime.utcnow() - timedelta(days=1),
            expires_at=datetime.utcnow() + timedelta(days=6)
        )
        
        # User 2 session
        session3 = Session(
            user_id=user2.user_id,
            token=generate_token(),
            created_at=datetime.utcnow() - timedelta(hours=5),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        # User 3 session
        session4 = Session(
            user_id=user3.user_id,
            token=generate_token(),
            created_at=datetime.utcnow() - timedelta(minutes=30),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        db_session.add_all([session1, session2, session3, session4])
        db_session.commit()
        print(f"Created 4 active sessions")
  
    except Exception as e:
        print(f"\n❌ Error during population: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    populate_database()