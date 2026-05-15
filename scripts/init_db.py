# this is for database initialization, not for production use
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db


def init_db():
    """Initialize the database."""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✓ Database initialized successfully!")
        print("✓ All tables created!")


if __name__ == "__main__":
    init_db()
