"""
Flask Extensions Initialization

This module initializes Flask extensions without immediately binding them
to an application instance (using the application factory pattern).
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask import redirect, url_for, flash
from functools import wraps
from typing import Callable, Any

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO(async_mode='threading')  # cors_allowed_origins configured per-environment in create_app

# Rate limiter — keyed by client IP
# Default: 200 per day, 50 per hour (overridden per-route where needed)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."


@login_manager.user_loader
def load_user(user_id: str) -> Any:
    """
    Load user from database during session.
    
    Args:
        user_id: User ID string from session
        
    Returns:
        User object or None if not found
    """
    from models import User
    return User.query.get(int(user_id))


def admin_required(f: Callable) -> Callable:
    """
    Decorator to require admin role for route access.
    
    Usage:
        @app.route('/admin')
        @admin_required
        def admin_dashboard():
            return "Admin only"
    
    Args:
        f: The function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def instructor_required(f: Callable) -> Callable:
    """
    Decorator to require instructor role for route access.
    
    Args:
        f: The function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        if not current_user.is_authenticated or current_user.role != 'instructor':
            flash('Access denied. Instructor only.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function