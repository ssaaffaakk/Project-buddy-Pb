"""
Application Configuration

This module defines configuration classes for different environments.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv
from sqlalchemy.pool import StaticPool

load_dotenv()

_PORT = os.environ.get('PORT', '5001')


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default).lower()).lower() in ('1', 'true', 'yes', 'on')


class Config:
    """Base configuration with common settings."""

    # ── Flask ──────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError('SECRET_KEY environment variable must be set in .env file')

    # ── Database ───────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_URI',
        'sqlite:///projectbuddy.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Upload size limit (52 MB — slightly above community 50 MB cap) ─────────
    MAX_CONTENT_LENGTH = 52 * 1024 * 1024   # 413 Payload Too Large if exceeded

    # ── Session ────────────────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)   # was 7 days — shortened
    SESSION_COOKIE_SECURE     = True
    SESSION_COOKIE_HTTPONLY   = True
    SESSION_COOKIE_SAMESITE   = 'Lax'
    SESSION_COOKIE_NAME       = '__Host-session'  # __Host- prefix requires Secure+no Domain

    # ── CSRF (Flask-WTF) ───────────────────────────────────────────────────────
    WTF_CSRF_ENABLED      = True
    WTF_CSRF_TIME_LIMIT   = 3600   # token valid 1 hour
    WTF_CSRF_SSL_STRICT   = False  # set True in production behind HTTPS

    # ── Email ──────────────────────────────────────────────────────────────────
    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER',
                                          os.environ.get('MAIL_USERNAME', ''))

    # ── Security ───────────────────────────────────────────────────────────────
    PASSWORD_RESET_TOKEN_EXPIRY = int(os.environ.get('PASSWORD_RESET_TOKEN_EXPIRY', 3600))

    # ── Admin (startup sync in app.py) ─────────────────────────────────────────
    ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL', '')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

    # ── Dev / mock seed data ─────────────────────────────────────────────────────
    MOCK_PASSWORD     = os.environ.get('MOCK_PASSWORD', '')
    MOCK_EMAIL_SUFFIX = os.environ.get('MOCK_EMAIL_SUFFIX', '@mock.projectbuddy.local')
    SEED_MOCK_DATA    = _env_bool('SEED_MOCK_DATA', True)

    # ── GitHub OAuth ─────────────────────────────────────────────────────────────
    GITHUB_CLIENT_ID     = os.environ.get('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
    GITHUB_REDIRECT_URI  = os.environ.get(
        'GITHUB_REDIRECT_URI',
        f'http://localhost:{_PORT}/auth/github/callback',
    )

    # ── Role rules ─────────────────────────────────────────────────────────────
    FACULTY_DOMAIN = os.environ.get('FACULTY_DOMAIN', '@faculty.university.edu')

    # ── Email API ─────────────────────────────────────────────────────────────────
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')

    # ── AI chatbot ───────────────────────────────────────────────────────────────
    GROQ_API_KEY      = os.environ.get('GROQ_API_KEY', '')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    # Default is the 8B model actually deployed (high free-tier quota, ~14,400 req/day).
    # Upgrade via GROQ_MODEL in .env — e.g. 'llama-3.3-70b-versatile' for higher quality (lower quota).
    GROQ_MODEL        = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')
    ANTHROPIC_MODEL   = os.environ.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')

    # ── Web push (VAPID) ─────────────────────────────────────────────────────────
    # Generate a keypair once with `py_vapid` and set these in .env.
    # Push is a no-op (gracefully skipped) when the keys are absent.
    VAPID_PUBLIC_KEY  = os.environ.get('VAPID_PUBLIC_KEY', '')
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
    VAPID_SUBJECT     = os.environ.get('VAPID_SUBJECT', 'mailto:surmeliisafak@gmail.com')

    # ── JSON API (/api/v1) ─────────────────────────────────────────────────────
    # OpenAPI spec + Swagger UI served by flask-smorest.
    API_TITLE = 'ProjectBuddy API'
    API_VERSION = 'v1'
    OPENAPI_VERSION = '3.0.3'
    OPENAPI_URL_PREFIX = '/api'
    OPENAPI_SWAGGER_UI_PATH = '/docs'
    OPENAPI_SWAGGER_UI_URL = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'
    # Bearer-token lifetime for the API (seconds; default 24h)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 86400))

    # ── Celery task queue ──────────────────────────────────────────────────────
    # With a broker: async tasks with retries (worker: celery -A celery_worker.celery worker).
    # Without: tasks run eagerly/in-thread — identical to the pre-queue behavior.
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', '') or os.environ.get('REDIS_URL', '')

    # ── Rate limiting ──────────────────────────────────────────────────────────
    # Use Redis if REDIS_URL is set (required for multi-worker deployments),
    # fall back to in-process memory for single-worker / dev environments.
    RATELIMIT_STORAGE_URI      = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_HEADERS_ENABLED  = True    # sends X-RateLimit-* headers

    # ── SocketIO CORS (production) ─────────────────────────────────────────────
    # Comma-separated allowed origins; read in create_app → socketio.init_app()
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '')

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL = 'INFO'


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_NAME   = 'session'   # __Host- requires HTTPS, not valid on http://localhost
    WTF_CSRF_SSL_STRICT   = False
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration."""

    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # A single shared connection so the schema created by the startup thread is
    # visible to request-handling connections. Without StaticPool each :memory:
    # connection is a separate empty database and every query 500s.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    SEED_MOCK_DATA = False   # deterministic tests — never seed demo data
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_NAME   = 'pb-session'  # __Host- prefix requires no proxy; Render uses proxy
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT   = False  # Render proxy strips/changes Referer, token check still active
    SEED_MOCK_DATA        = False  # never seed mock data in production
