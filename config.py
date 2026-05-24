"""
Application Configuration

This module defines configuration classes for different environments.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

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
    IUS_FACULTY_DOMAIN = os.environ.get('IUS_FACULTY_DOMAIN', '@faculty.ius.edu.ba')

    # ── AI chatbot ───────────────────────────────────────────────────────────────
    GROQ_API_KEY      = os.environ.get('GROQ_API_KEY', '')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    GROQ_MODEL        = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')
    ANTHROPIC_MODEL   = os.environ.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')

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
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT   = True   # enforce HTTPS Referer check for CSRF on prod
