"""
Admin User Creation Script

This script creates an initial admin user for the application.
Uses environment variables from .env file for admin credentials.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import User


def create_admin():
    """Create an admin user from environment variables."""
    app = create_app()
    with app.app_context():
        admin_email = app.config.get('ADMIN_EMAIL')
        admin_password = app.config.get('ADMIN_PASSWORD')
        if not admin_email or not admin_password:
            print("✗ Set ADMIN_EMAIL and ADMIN_PASSWORD in .env")
            return
        
        # Check if admin already exists
        admin = User.query.filter_by(email=admin_email).first()
        if admin:
            print(f"✓ Admin user already exists with email: {admin_email}")
            return
        
        # Create admin user
        admin = User(
            first_name="Admin",
            last_name="User",
            email=admin_email,
            role="admin",
        )
        admin.set_password(admin_password)
        
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin user created successfully!")
        print(f"  Email: {admin_email}")
        print("  Password: (set from ADMIN_PASSWORD environment variable)")


if __name__ == "__main__":
    create_admin()