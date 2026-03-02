"""
Database Setup Script for Resume Verifier API

Creates all database tables using the Flask application factory so that
Flask-SQLAlchemy models are registered correctly.

Usage (from project root):
    python database/setup_database.py
"""
import sys
import os

# Ensure project root is on the Python path so resumeverifier can be imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resumeverifier import create_app  # pylint: disable=wrong-import-position
from resumeverifier.extensions import db  # pylint: disable=wrong-import-position


def setup_database():
    """
    Drop all existing tables and recreate the schema from the ORM models.

    Creates a Flask application context to ensure SQLAlchemy is fully
    initialised before calling ``db.create_all()``.
    """
    print("=" * 60)
    print("Resume Verifier API - Database Setup")
    print("=" * 60)

    app = create_app()
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        print("Dropping existing tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        tables = db.engine.table_names() if hasattr(db.engine, "table_names") else list(
            db.metadata.tables.keys()
        )
        print("\nTables created:")
        for table in tables:
            print(f"  ✓ {table}")

    print("\nDatabase setup completed successfully!")
    print("Next step: run 'python database/populate_database.py' to add sample data.")


if __name__ == "__main__":
    setup_database()
