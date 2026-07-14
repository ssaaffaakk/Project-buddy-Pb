"""
Flask Application Factory

This module creates and configures the Flask application instance
using the application factory pattern.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
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

    # ProxyFix: trust one level of reverse proxy headers (Render, Heroku, etc.)
    # Without this: url_for generates http:// instead of https://,
    # rate limiting sees proxy IP instead of real client IP,
    # and OAuth/password-reset links break.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Error monitoring (no-op unless SENTRY_DSN is set)
    _init_sentry(app)

    # Initialize extensions
    _initialize_extensions(app)
    
    # Create instance folder
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Celery: bind broker config (eager/no-op without a broker) BEFORE the
    # blueprints import services.tasks.
    from celery_app import init_celery
    init_celery(app)

    # Register blueprints
    _register_blueprints(app)

    # JSON API v1 (+ OpenAPI docs at /api/docs)
    _register_api(app)

    # Prometheus metrics: request RED metrics + domain gauges at /metrics
    from services.metrics import init_metrics
    init_metrics(app)

    # Slow-query logging (statements only — never parameters)
    from services.db_profiler import init_db_profiler
    init_db_profiler(app)

    # CLI: retrain the teammate/project recommender  →  flask train-recommender
    @app.cli.command("train-recommender")
    def train_recommender_cmd():
        """Retrain the ML recommender on current data and save the artifact."""
        from services.ml.train_recommender import train
        train()

    # CLI: run the ELT pipeline into the dw_* star schema  →  flask run-etl
    @app.cli.command("run-etl")
    def run_etl_cmd():
        """Load the data warehouse (dims + facts + daily metrics) and run
        data-quality checks. Also scheduled nightly via Celery beat."""
        from services.etl import run_pipeline
        summary = run_pipeline()
        print(f"ETL OK: {summary}")

    # CLI: model registry — list archived versions / roll back / drift check
    @app.cli.command("model-versions")
    def model_versions_cmd():
        """List archived recommender versions (newest first)."""
        from services.ml.train_recommender import list_versions
        versions = list_versions()
        print("\n".join(versions) if versions else "no archived versions yet")

    import click

    @app.cli.command("rollback-recommender")
    @click.argument("version")
    def rollback_recommender_cmd(version):
        """Restore an archived model version as the serving model."""
        from services.ml.train_recommender import rollback
        print(f"restored version {rollback(version)} — serving it now")

    @app.cli.command("check-drift")
    def check_drift_cmd():
        """Compare live feature distribution against the training snapshot."""
        from services.ml.drift import compute_drift
        report = compute_drift()
        if report:
            print(f"drift {report['status']}: score={report['score']} "
                  f"over {report['n_pairs']} pairs")
        else:
            print("drift check skipped (no baseline or no population)")

    @app.cli.command("send-digest")
    def send_digest_cmd():
        """Send the weekly recommendation digest now (also runs via beat)."""
        from services.digest import send_weekly_digest
        print(f"digest: {send_weekly_digest()}")

    @app.route("/favicon.ico")
    def favicon():
        from flask import send_from_directory
        return send_from_directory(
            os.path.join(app.root_path, "static", "images"),
            "favicon-32x32.png",
            mimetype="image/png",
        )

    _register_context_processors(app)

    # Set up shell context
    _setup_shell_context(app)

    # Configure logging
    _configure_logging(app)

    # Start background scheduler (skipped in testing)
    if not app.config.get("TESTING"):
        _start_scheduler(app)

    return app


def _init_sentry(app: Flask) -> None:
    """Initialize Sentry error monitoring when SENTRY_DSN is configured.

    Graceful no-op when the DSN is unset or the SDK isn't installed, so
    development environments need zero setup.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
            send_default_pii=False,  # never ship user emails/IPs to a third party
        )
        app.logger.info("Sentry error monitoring initialized.")
    except ImportError:
        app.logger.warning("SENTRY_DSN set but sentry-sdk not installed — skipping.")
    except Exception as e:
        app.logger.warning("Sentry init failed: %s", e)


def _initialize_extensions(app: Flask) -> None:
    """Initialize Flask extensions with the app."""
    from extensions import limiter, csrf
    import models  # noqa: F401 — side-effect import: registers all models before migrate sees them

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    limiter.init_app(app)
    csrf.init_app(app)

    # Restrict SocketIO CORS: allow only our own origin in production,
    # all origins in development (needed for hot-reload / test clients).
    # Use app.debug (set by config class) rather than FLASK_ENV env var so
    # wsgi.py's ProductionConfig is the single source of truth.
    _raw_origins = os.environ.get("CORS_ORIGINS", "")
    if not app.debug:
        origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
        if not origins:
            # Render sets RENDER_EXTERNAL_URL automatically; empty CORS_ORIGINS
            # must not become [] or Socket.IO rejects the browser connection.
            render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
            origins = [render_url] if render_url else "*"
        cors_origins = origins
    else:
        cors_origins = "*"
    # Redis message queue: required when running multiple Gunicorn workers so
    # SocketIO events (including voice signaling) are broadcast across all
    # processes. Falls back to None (in-process only) when REDIS_URL is unset.
    redis_url = os.environ.get("REDIS_URL") or None
    socketio.init_app(
        app,
        cors_allowed_origins=cors_origins,
        message_queue=redis_url,
    )

    # Disable Secure cookie flag outside of production
    # (allows login over plain http://localhost in dev)
    if not app.config.get("TESTING") and app.debug:
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
        # Content Security Policy:
        # unsafe-inline is required for both script and style because the
        # templates use inline event handlers (onclick=) and inline style
        # attributes throughout. frame-ancestors blocks clickjacking.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            # cdn.jsdelivr.net in style-src: Swagger UI (/api/docs) loads its CSS there
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss: https://cdn.jsdelivr.net; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';"
        )
        # Restrict browser API access (mic + camera + screen share for WebRTC rooms)
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), display-capture=(self), "
            "geolocation=(), payment=(), usb=()"
        )
        # Isolate browsing context — prevents cross-origin window attacks
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # Prevent other sites from embedding our resources (API, static files)
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # HSTS — only sent in production (where HTTPS is enforced)
        if not app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        # ── Cache-Control per path ─────────────────────────────────────────────
        from flask import request as _req
        path = _req.path
        if path == "/favicon.ico" or (
            path.startswith("/static/images/")
            and ("favicon" in path or "apple-touch-icon" in path)
        ):
            # Tab icons — short cache so logo updates propagate
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path.startswith("/static/images/") or path.startswith("/static/images"):
            # Logos, icons — almost never change
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/static/css/") or path.startswith("/static/js/"):
            # CSS/JS — versioned via ?v= param in templates, 1 week fallback
            response.headers["Cache-Control"] = "public, max-age=604800"
        elif path.startswith("/static/uploads/"):
            # User-uploaded files — short cache, content can change
            response.headers["Cache-Control"] = "private, max-age=3600"
        elif path.startswith("/static/"):
            # Other static assets (fonts, etc.)
            response.headers["Cache-Control"] = "public, max-age=86400"
        else:
            # HTML pages — always fresh (login state, notifications, etc.)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
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

    # ── Idle-session timeout: sign out after SESSION_IDLE_TIMEOUT_MIN of ──────
    # inactivity. Timer-driven background requests (the 30s notifications poll,
    # the chat fallback poll) CHECK expiry but don't RESET the clock — so a user
    # who walks away with a tab open still gets signed out, while any real
    # click/navigation keeps the session alive.
    from time import time as _now
    from flask import session as _session
    from flask_login import current_user as _cu, logout_user as _logout_user

    _IDLE_EXEMPT_ENDPOINTS = {
        'main.get_notifications',       # polled every 30s from every page
        'study_groups.poll_messages',   # chat fallback poll / reconnect catch-up
        'main.service_worker',          # browser-driven SW update checks
        'main.manifest',                # PWA manifest fetch — not user activity
    }

    @app.before_request
    def _enforce_idle_timeout():
        timeout_min = app.config.get('SESSION_IDLE_TIMEOUT_MIN', 30)
        if not timeout_min or not _cu.is_authenticated:
            return
        # Leave the realtime transport and static assets out of this entirely.
        p = _req.path
        if p.startswith('/socket.io') or p.startswith('/static'):
            return
        now = _now()
        last = _session.get('_last_active')
        if last is not None and now - float(last) > timeout_min * 60:
            _logout_user()
            _session.clear()
            _flash('You were signed out after a period of inactivity. Please log in again.', 'error')
            return  # proceed anonymously; @login_required redirects to login
        if last is None or _req.endpoint not in _IDLE_EXEMPT_ENDPOINTS:
            _session['_last_active'] = now

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
    # Importing routes.messages also registers its @socketio.on('join_dm') handler.
    from routes.messages import messages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(study_groups_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(messages_bp)

    # Register SocketIO voice-chat event handlers
    import routes.voice  # noqa: F401  — side-effect: registers @socketio.on handlers

    # Schema + seed on startup.
    # Must run in a REAL OS thread (not a greenlet / tpool) because:
    #   - tpool.execute() internally calls hub.switch()
    #   - At module-import time the eventlet hub loop hasn't started yet
    #   - hub.switch() from the hub's own greenlet raises
    #     "do not call blocking functions from the mainloop"
    # eventlet.patcher.original() gives us the unpatched threading module
    # so we get a genuine OS thread, completely outside eventlet's hub.
    def _run_startup_tasks():
        with app.app_context():
            _apply_schema(app)
            _ensure_feature_columns(app)
            _seed_badges()
            _sync_admin()
            _sync_avatar_urls()
            _seed_mock_if_empty()
            _fix_broken_passwords()

    import eventlet.patcher as _ep
    _real_Thread = _ep.original('threading').Thread
    _t = _real_Thread(target=_run_startup_tasks, daemon=True)
    _t.start()
    _t.join()  # OS-level block — fine here because hub isn't serving yet


def _register_api(app: Flask) -> None:
    """Register the versioned JSON API (flask-smorest) + OpenAPI docs.

    The blueprint is CSRF-exempt: browsers' session cookies are only accepted
    on read endpoints; writes require a Bearer token, which cross-site pages
    cannot attach — so the exemption doesn't reopen CSRF.
    """
    from flask_smorest import Api
    from routes.api_v1 import blp as api_blp
    from extensions import csrf

    api = Api(app)
    api.spec.components.security_scheme(
        "bearerAuth", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    )
    api.register_blueprint(api_blp)
    csrf.exempt(api_blp)


def _apply_schema(app: Flask) -> None:
    """Apply database schema.

    Alembic is NOT a complete source of truth in this project, despite what the
    old docstring here claimed. The baseline migration (3f60331bcca5) is an empty
    stamp that creates nothing, and 68ce403fbd55 ("add study_group_notes") is
    empty too — `study_group_notes` has no migration at all. Building from
    migrations alone dies on the first ALTER with "NoSuchTableError: users".
    create_all() is what actually builds tables; Alembic only carries deltas on
    top of it. So create_all() stays — dropping it would break a fresh deploy.

    What was genuinely broken is that Alembic failures were swallowed. create_all()
    built the dw_* tables from models.py before their migration existed, so every
    later `db upgrade` died on "dw_dim_user already exists" — and since the error
    was only ever a log line, ten migrations silently never applied, leaving the
    16 hot-path indexes from c3e8f5a71d29 absent from the database entirely.

    - Fresh DB (any env): build from the models, then stamp head, so the
      migrations creating those same tables can never collide with create_all().
    - Existing DB, production: an Alembic failure is FATAL. A drifted chain must
      fail the deploy rather than limp along unnoticed for ten migrations.
    - Existing DB, development: failures stay non-fatal.
    - Testing: create_all() only — conftest wants a migration-free schema.
    """
    from flask_migrate import stamp as db_stamp, upgrade as db_upgrade
    from sqlalchemy import inspect as sa_inspect

    if app.config.get("TESTING"):
        db.create_all()
        return

    if not sa_inspect(db.engine).has_table("alembic_version"):
        db.create_all()
        db_stamp()
        app.logger.info("Fresh database built from models and stamped head.")
        return

    if not app.debug:  # production — app.debug is the prod signal (see CORS note)
        db_upgrade()   # deliberately unguarded: a drifted chain must fail the deploy
        app.logger.info("Database migrations applied.")
    else:
        try:
            db_upgrade()
            app.logger.info("Database migrations applied.")
        except Exception as e:
            app.logger.warning("Migration step skipped: %s", e)

    # Load-bearing: models whose migration is empty or missing (study_group_notes)
    # exist only because of this. Idempotent — existing tables are skipped.
    db.create_all()


def _ensure_feature_columns(app: Flask) -> None:
    """Backfill columns added to *existing* tables when `db upgrade` was skipped.

    create_all() (the boot-time safety net) creates missing TABLES but never
    ALTERs existing ones, so a column added by a migration is absent on any DB
    whose migration chain didn't fully apply. When a mapped column is missing,
    every query on that model raises a DB-API error (ProgrammingError on
    PostgreSQL, OperationalError on SQLite) — e.g. a missing `users.timezone`
    500s essentially every page. This idempotently adds those columns so the
    app self-heals on the next restart regardless of migration state.
    """
    from sqlalchemy import inspect as sa_inspect, String, DateTime, Integer, Boolean

    # (table, column, SQLAlchemy type) for every column this app added to a
    # pre-existing table. New TABLES are handled by create_all and need no entry.
    wanted = [
        ("users", "timezone", String(64)),
        ("project_tasks", "due_date", DateTime()),
        ("direct_messages", "attachment_id", Integer()),
        ("direct_messages", "shared_post_id", Integer()),
        ("conversations", "a_archived", Boolean()),
        ("conversations", "b_archived", Boolean()),
        ("conversations", "a_pinned", Boolean()),
        ("conversations", "b_pinned", Boolean()),
    ]
    try:
        insp = sa_inspect(db.engine)
        existing_tables = set(insp.get_table_names())
        dialect = db.engine.dialect
        for table, column, coltype in wanted:
            if table not in existing_tables:
                continue  # whole table missing → create_all will build it correctly
            cols = {c["name"] for c in insp.get_columns(table)}
            if column in cols:
                continue
            ddl_type = coltype.compile(dialect=dialect)
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}')
            app.logger.warning("Backfilled missing column %s.%s (%s).", table, column, ddl_type)
    except Exception as e:
        app.logger.warning("Feature-column backfill skipped: %s", e)


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


def _sync_avatar_urls() -> None:
    """Backfill avatar_url when a file exists on disk but the DB row is empty."""
    import os
    import re
    from flask import current_app
    from models import User

    project_root = os.path.dirname(os.path.abspath(__file__))
    avatars_dir = os.path.join(project_root, "static", "uploads", "avatars")
    if not os.path.isdir(avatars_dir):
        return

    pattern = re.compile(r"^user_(\d+)\.(jpg|jpeg|png|webp)$", re.IGNORECASE)
    updated = 0
    for name in os.listdir(avatars_dir):
        match = pattern.match(name)
        if not match:
            continue
        user = db.session.get(User, int(match.group(1)))
        if not user or user.avatar_url:
            continue
        user.avatar_url = f"/static/uploads/avatars/{name}"
        updated += 1

    if updated:
        db.session.commit()
        current_app.logger.info("Backfilled avatar_url for %d user(s).", updated)


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
            last_name='Admin',
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

    # i18n: expose _() for translation plus locale metadata in every template.
    from services.i18n import translate, get_locale, LANGUAGES
    app.jinja_env.globals["_"] = translate

    @app.context_processor
    def inject_i18n():
        return {
            "_": translate,
            "current_locale": get_locale(),
            "LANGUAGES": LANGUAGES,
        }

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

    @app.context_processor
    def inject_nav_active():
        """Highlight the current page in the shared user sidebar."""
        from flask import request

        path = request.path.rstrip("/") or "/"
        active = ""

        if path.startswith("/admin"):
            active = "admin"
        elif path == "/dashboard":
            active = "dashboard"
        elif path == "/projects-page" or path.startswith("/projects/"):
            active = "projects"
        elif path == "/teammates":
            active = "teammates"
        elif path == "/instructor":
            active = "instructor"
        elif path.startswith("/community"):
            active = "community"
        elif path.startswith("/study-groups"):
            active = "study_groups"
        elif path.startswith("/chatbot"):
            active = "chatbot"
        elif path == "/quiz":
            active = "quiz"
        elif path == "/post-project-page":
            active = "post_project"
        elif path == "/my-projects":
            active = "my_projects"
        elif path.startswith("/messages"):
            active = "messages"
        elif path == "/saved":
            active = "saved"
        elif path == "/availability":
            active = "availability"
        elif path in ("/profile", "/edit-profile") or path.startswith("/user/"):
            active = "profile"
        elif path.startswith("/chat"):
            active = "support_chat"
        elif path.startswith("/report-issue"):
            active = "report_issue"

        return {"nav_active": active}

    @app.context_processor
    def inject_dm_unread():
        """Expose the current user's unread direct-message count so the sidebar
        can render a badge on the Messages link. One indexed COUNT query."""
        from flask_login import current_user
        if not current_user.is_authenticated:
            return {}
        try:
            from models import Conversation, DirectMessage
            n = (DirectMessage.query
                 .join(Conversation, Conversation.id == DirectMessage.conversation_id)
                 .filter((Conversation.user_a_id == current_user.id) |
                         (Conversation.user_b_id == current_user.id))
                 .filter(DirectMessage.sender_id != current_user.id,
                         DirectMessage.is_read == False)  # noqa: E712
                 .count())
        except Exception:
            # A failed query (e.g. the table isn't there yet on a half-migrated
            # DB) leaves the session needing a rollback; without it every later
            # query in this request would raise PendingRollbackError.
            db.session.rollback()
            n = 0
        return {"dm_unread": n}


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
    """Start a background OS thread that runs the deadline checker every hour.

    Uses a genuine OS thread (not an eventlet greenlet) so the scheduler
    never touches the eventlet hub / mainloop.  The thread sleeps via the
    *real* time.sleep() — completely outside eventlet — and psycopg2 uses
    C-level blocking sockets, which are also unaffected by the hub.

    Why NOT socketio.start_background_task / eventlet.spawn:
      socketio.sleep() (and any sleep rooted in eventlet.sleep) internally
      calls hub.switch().  When that switch is attempted before or from the
      hub's own greenlet the runtime raises
      "do not call blocking functions from the mainloop".
      A real OS thread has no greenlet context and bypasses this check
      entirely.
    """
    # In Flask debug mode the reloader forks a child. WERKZEUG_RUN_MAIN is
    # set only in the child (the real server). Skip the parent to avoid two
    # scheduler instances fighting over the same DB.
    if app.debug and not os.environ.get("WERKZEUG_RUN_MAIN"):
        return

    import eventlet.patcher as _ep
    _real_Thread = _ep.original('threading').Thread
    _real_sleep  = _ep.original('time').sleep

    def _scheduler_loop():
        while True:
            _real_sleep(3600)       # real OS sleep — hub not involved
            with app.app_context():
                try:
                    from services.deadline_checker import flag_overdue_projects
                    flag_overdue_projects()
                    app.logger.info("Deadline check completed.")
                except Exception as e:
                    app.logger.exception("Deadline checker failed: %s", e)

    t = _real_Thread(target=_scheduler_loop, daemon=True, name="deadline-scheduler")
    t.start()
    app.logger.info("Background scheduler started (deadline check every 1h).")


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5001))
    socketio.run(app, debug=app.debug, host="0.0.0.0", port=port,
                 allow_unsafe_werkzeug=app.debug)
