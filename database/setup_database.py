"""
Database Setup Script for Resume Verifier API

This script creates all database tables and initializes the database schema.
Run this before populating the database with test data.

Usage:
    python setup_database.py
"""

import os
from sqlalchemy import create_engine
from models import Base, User, ResumeProject, Experience, VerificationRequest, ShareLink, Session

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///resume_verifier.db')


def setup_database():
    """
    Create database engine and initialize all tables.
    
    This function:
    1. Creates a connection to the database
    2. Drops all existing tables (if any)
    3. Creates all tables defined in models.py
    4. Confirms successful creation
    """
    print("=" * 60)
    print("Resume Verifier API - Database Setup")
    print("=" * 60)
    print()
    
    # Create database engine
    print(f"Database URL: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL, echo=True)
    
    print("\n" + "-" * 60)
    print("Dropping existing tables (if any)...")
    print("-" * 60)
    Base.metadata.drop_all(engine)
    
    print("\n" + "-" * 60)
    print("Creating all tables...")
    print("-" * 60)
    Base.metadata.create_all(engine)
    
    print("\n" + "=" * 60)
    print("Database setup completed successfully!")
    print("=" * 60)
    print("\nTables created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  ✓ {table_name}")
    
    print("\nNext step: Run 'python populate_database.py' to add sample data")
    print()
    
    return engine


if __name__ == "__main__":
    setup_database()