"""
Celery worker entry point.

    celery -A celery_worker.celery worker --beat --loglevel=info

Builds the Flask app (for config + DB), binds Celery to it, and imports the
task module so tasks register. FLASK_ENV=production selects ProductionConfig.
"""

import os

from app import create_app
from celery_app import celery, init_celery
from config import DevelopmentConfig, ProductionConfig

_cfg = (ProductionConfig
        if os.environ.get("FLASK_ENV") == "production"
        else DevelopmentConfig)

flask_app = create_app(_cfg)
init_celery(flask_app)

import services.tasks  # noqa: E402,F401 — registers the task definitions

__all__ = ["celery"]
