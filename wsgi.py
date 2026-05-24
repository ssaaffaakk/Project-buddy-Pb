"""
WSGI entry point for production deployment.

Usage (gunicorn + eventlet):
    gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app

The app must be named `app` so Flask-SocketIO's monkey-patching fires
before any stdlib imports.

This file is the production entry point — it always uses ProductionConfig.
Never import DevelopmentConfig here; use `python app.py` for local dev.
"""

import eventlet
eventlet.monkey_patch()

from app import create_app
from config import ProductionConfig

app = create_app(ProductionConfig)
