"""
Flask Extensions Initialization

This module initializes Flask extensions without immediately binding them
to an application instance (using the application factory pattern).
"""

import os
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
# async_mode='eventlet' matches the eventlet worker used in wsgi.py + gunicorn.
# cors_allowed_origins and message_queue are set per-environment in create_app.
socketio = SocketIO(async_mode='eventlet')

# Rate limiter — keyed by client IP
# Defaults sized for normal authenticated browsing (each page view triggers
# several requests). Sensitive routes (login etc.) set stricter per-route
# limits; high-frequency polling endpoints are @limiter.exempt.
# Uses Redis when REDIS_URL is set (production/multi-worker), falls back to
# in-process memory for dev / single-worker deployments.
_ratelimit_storage = os.environ.get('REDIS_URL', 'memory://')
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10000 per day", "1500 per hour"],
    storage_uri=_ratelimit_storage,
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