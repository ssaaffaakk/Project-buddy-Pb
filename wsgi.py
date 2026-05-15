"""
WSGI entry point for production deployment.

Usage (gunicorn + eventlet):
    gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT wsgi:app

The app must be named `app` so Flask-SocketIO's monkey-patching fires
before any stdlib imports.
"""

import eventlet
eventlet.monkey_patch()

import os
from app import create_app
from config import ProductionConfig, DevelopmentConfig

_cfg = ProductionConfig if os.environ.get("FLASK_ENV") == "production" else DevelopmentConfig
app = create_app(_cfg)
