"""
Flask Application Factory

This module creates and configures the Flask application instance
using the application factory pattern.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from config import Config
from extensions import db, login_manager, socketio, migrate


def create_app(config_class=None):
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class to use. Defaults to DevelopmentConfig.

    Returns:
        Flask: Configured Flask application instance.
    """
    if config_class is None:
        from config import DevelopmentConfig
        config_class = DevelopmentConfig
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    _initialize_extensions(app)
    
    # Create instance folder
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Register blueprints
    _register_blueprints(app)

    _register_context_processors(app)

    # Set up shell context
    _setup_shell_context(app)

    # Configure logging
    _configure_logging(app)

    # Start background scheduler (skipped in testing)
    if not app.config.get("TESTING"):
        _start_scheduler(app)

    return app


def _initialize_extensions(app: Flask) -> None:
    """Initialize Flask extensions with the app."""
    from extensions import limiter, csrf
    import models  # ensure all models are registered before migrate sees them

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    limiter.init_app(app)
    csrf.init_app(app)

    # Restrict SocketIO CORS: allow only our own origin in production,
    # all origins in development (needed for hot-reload / test clients).
    is_prod = os.environ.get("FLASK_ENV") == "production"
    cors_origins = (
        os.environ.get("CORS_ORIGINS", "").split(",") if is_prod else "*"
    )
    # Redis message queue: required when running multiple Gunicorn workers so
    # SocketIO events (including voice signaling) are broadcast across all
    # processes. Falls back to None (in-process only) when REDIS_URL is unset.
    redis_url = os.environ.get("REDIS_URL") or None
    socketio.init_app(app, cors_allowed_origins=cors_origins, message_queue=redis_url)

    # Disable Secure cookie flag outside of production
    # (allows login over plain http://localhost in dev)
    if not app.config.get("TESTING") and os.environ.get("FLASK_ENV") != "production":
        app.config["SESSION_COOKIE_SECURE"] = False

    # ── Per-request CSP nonce ─────────────────────────────────────────────────
    import secrets as _secrets
    from flask import g as _g

    @app.before_request
    def _generate_csp_nonce():
        """Generate a fresh random nonce for every request.
        Templates access it via {{ csp_nonce }} (injected by context processor).
        """
        _g.csp_nonce = _secrets.token_urlsafe(16)

    # ── Security headers on every response ────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Disallow embedding in iframes (clickjacking)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        # Legacy XSS filter (modern browsers ignore this, kept for old IE/Edge)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Don't send full URL in Referer header to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Remove server fingerprint
        response.headers.pop("Server", None)
        # Content Security Policy — nonce-based (no unsafe-inline):
        #   Every inline <script nonce="…"> and <style nonce="…"> must carry
        #   the per-request nonce generated in _generate_csp_nonce().
        nonce = getattr(_g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
            f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            "media-src 'self' blob:; "
            "frame-ancestors 'none';"
        )
        # HSTS — only sent in production (where HTTPS is enforced)
        if os.environ.get("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response

    # ── Rate-limit exceeded: return flash+redirect instead of raw JSON ─────────
    from flask import request as _req, redirect as _redir, flash as _flash, url_for as _url_for
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def ratelimit_handler(e):
        _flash('Too many attempts. Please wait a moment and try again.', 'error')
        return _redir(_req.referrer or _url_for('auth.login'))

    # ── CSRF failure: redirect with flash instead of raw 400 JSON ─────────────
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        _flash('Session expired. Please try again.', 'error')
        return _redir(_req.referrer or _url_for('auth.login'))

    # ── Generic HTTP error pages ───────────────────────────────────────────────
    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("500 error: %s", e)
        return render_template("errors/500.html"), 500


def _register_blueprints(app: Flask) -> None:
    """Register Flask blueprints."""
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.projects import projects_bp
    from routes.users import users_bp
    from routes.admin import admin_bp
    from routes.chat import chat_bp
    from routes.community import community_bp
    from routes.study_groups import study_groups_bp
    from routes.chatbot import chatbot_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(study_groups_bp)
    app.register_blueprint(chatbot_bp)

    # Register SocketIO voice-chat event handlers
    import routes.voice  # noqa: F401  — side-effect: registers @socketio.on handlers

    # Create tables, seed badges, sync admin, and seed mock data on first run
    with app.app_context():
        db.create_all()
        _seed_badges()
        _sync_admin()
        _seed_mock_if_empty()
        _fix_broken_passwords()


def _seed_badges() -> None:
    """Create default badges if they don't exist."""
    from models import Badge
    defaults = [
        ("first step", "Complete your first project", "[1]"),
        ("veteran", "Complete 5 projects", "[5]"),
        ("expert", "Receive 10 skill endorsements", "[E]"),
    ]
    for name, desc, icon in defaults:
        if not Badge.query.filter_by(name=name).first():
            db.session.add(Badge(name=name, description=desc, icon=icon))
    db.session.commit()


def _sync_admin() -> None:
    """Create or update the admin account from .env credentials."""
    from flask import current_app
    from models import User
    email = current_app.config.get('ADMIN_EMAIL')
    password = current_app.config.get('ADMIN_PASSWORD')
    if not email or not password:
        return
    admin = User.query.filter_by(email=email).first()
    if admin:
        admin.set_password(password)
        admin.role = 'admin'
    else:
        admin = User(
            first_name='Admin',
            last_name='IUS',
            email=email,
            role='admin',
        )
        admin.set_password(password)
        db.session.add(admin)
    db.session.commit()


def _seed_mock_if_empty() -> None:
    """Seed realistic mock data the first time the app starts (or if DB is empty)."""
    from flask import current_app
    if not current_app.config.get('SEED_MOCK_DATA', True):
        return
    try:
        from services.mock_data import seed_mock_data
        seed_mock_data()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Mock data seeding skipped: %s", e)


def _fix_broken_passwords() -> None:
    """Auto-fix mock accounts whose passwords got corrupted or use an
    unsupported hash algorithm (e.g. scrypt on Python 3.9 / LibreSSL).
    Safe to run every startup — only re-hashes when the password doesn't verify."""
    from flask import current_app
    from models import User
    mock_password = current_app.config.get('MOCK_PASSWORD', 'Mock@123')
    mock_suffix = current_app.config.get('MOCK_EMAIL_SUFFIX', '@mock.projectbuddy.local')
    fixed = 0
    for user in User.query.filter(User.email.like(f'%{mock_suffix}')).all():
        try:
            needs_fix = not user.check_password(mock_password)
        except (AttributeError, ValueError):
            # hash algorithm not supported on this platform (e.g. scrypt + LibreSSL)
            needs_fix = True
        if needs_fix:
            user.set_password(mock_password)
            fixed += 1
    if fixed:
        db.session.commit()


def _register_context_processors(app: Flask) -> None:
    """Inject variables available in every template."""

    @app.context_processor
    def inject_csp_nonce():
        """Make the per-request CSP nonce available as {{ csp_nonce }}."""
        from flask import g
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.context_processor
    def inject_admin_sidebar():
        """Inject admin sidebar badge counts on all admin templates."""
        from flask_login import current_user
        if not current_user.is_authenticated or not current_user.is_admin():
            return {}
        from models import Report, Chat
        return {
            "admin_pending_reports": Report.query.filter_by(status="pending").count(),
            "admin_open_chat_count": Chat.query.filter_by(status="open").count(),
        }


def _setup_shell_context(app: Flask) -> None:
    """Set up Flask shell context."""
    @app.shell_context_processor
    def make_shell_context():
        """Add common objects to shell context."""
        return {"db": db}


def _configure_logging(app: Flask) -> None:
    """Configure application logging."""
    if not app.debug and not app.testing:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        
        file_handler = RotatingFileHandler(
            "logs/app.log", maxBytes=10240000, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info("Application startup")


def _start_scheduler(app: Flask) -> None:
    """Start APScheduler to run background tasks periodically.

    Uses BackgroundScheduler (thread-based).  Guards against double-start:
    Flask debug mode spawns a reloader child process — we only want the
    scheduler running in the actual worker, not the reloader parent.
    """
    # In Flask debug mode the reloader forks a child. WERKZEUG_RUN_MAIN is
    # set only in the child (the real server). Skip the parent to avoid two
    # scheduler instances fighting over the same DB.
    if app.debug and not os.environ.get("WERKZEUG_RUN_MAIN"):
        return

    from apscheduler.schedulers.background import BackgroundScheduler

    def _run_deadline_check():
        with app.app_context():
            try:
                from services.deadline_checker import flag_overdue_projects
                flag_overdue_projects()
                app.logger.info("Deadline check completed.")
            except Exception as e:
                app.logger.exception("Deadline checker failed: %s", e)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run_deadline_check,
        trigger="interval",
        hours=1,
        id="deadline_checker",
        replace_existing=True,
    )
    scheduler.start()
    app.logger.info("Background scheduler started (deadline check every 1h).")


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    socketio.run(app, debug=app.debug, host="0.0.0.0", port=port,
                 allow_unsafe_werkzeug=os.environ.get("FLASK_ENV") != "production")
