"""
Background tasks (Celery) + broker-aware dispatch helpers.

Routes never call .delay() directly — they call dispatch_push()/dispatch_email(),
which pick the right execution mode:

  broker configured → task queued to Redis, executed on the worker with retries
  no broker         → background OS thread running the same function
                      (identical to the pre-queue behavior; requests never block)

Each task enters a Flask app context on the worker via _flask_context(), so
config, DB, and services work exactly as they do in the web process.
"""

import logging
import os
from contextlib import contextmanager

from celery_app import celery, has_broker

logger = logging.getLogger(__name__)

_worker_app = None


@contextmanager
def _flask_context():
    """Yield inside a Flask app context, creating a worker-owned app if needed."""
    from flask import has_app_context
    if has_app_context():
        yield
        return
    global _worker_app
    if _worker_app is None:
        from app import create_app
        from config import DevelopmentConfig, ProductionConfig
        cfg = (ProductionConfig
               if os.environ.get("FLASK_ENV") == "production"
               else DevelopmentConfig)
        _worker_app = create_app(cfg)
    with _worker_app.app_context():
        yield


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery.task(name="tasks.send_push", bind=True, max_retries=3, default_retry_delay=30)
def send_push_task(self, user_id, title, body, url="/dashboard"):
    """Deliver a web push to all of a user's subscribed browsers."""
    with _flask_context():
        from services.push_service import notify_user
        try:
            notify_user(user_id, title, body, url=url)
        except Exception as exc:  # pragma: no cover — notify_user rarely raises
            raise self.retry(exc=exc)


@celery.task(name="tasks.send_email", bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, recipient, subject, body, is_html=False):
    """Deliver a transactional email via the Brevo HTTP API."""
    with _flask_context():
        from routes.email import deliver_email
        if not deliver_email(recipient, subject, body, is_html=is_html):
            raise self.retry(exc=RuntimeError("Brevo delivery failed"))


@celery.task(name="tasks.check_deadlines")
def check_deadlines_task():
    """Auto-complete projects whose deadline has passed (idempotent)."""
    with _flask_context():
        from services.deadline_checker import flag_overdue_projects
        flag_overdue_projects()


@celery.task(name="tasks.retrain_recommender")
def retrain_recommender_task():
    """Weekly retrain on accumulated data. train() raises when there isn't
    enough signal — logged and skipped, never retried in a loop."""
    with _flask_context():
        from services.ml.train_recommender import train
        try:
            metrics = train(verbose=False)
            logger.info("recommender retrained: version=%s roc_auc=%s",
                        metrics.get("version"), metrics.get("roc_auc"))
        except RuntimeError as e:
            logger.info("recommender retrain skipped: %s", e)


@celery.task(name="tasks.check_model_drift")
def check_model_drift_task():
    """Daily feature-drift check against the training snapshot."""
    with _flask_context():
        from services.ml.drift import compute_drift
        compute_drift()


@celery.task(name="tasks.send_weekly_digest")
def send_weekly_digest_task():
    """Weekly per-user recommendation digest (in-app notification + push)."""
    with _flask_context():
        from services.digest import send_weekly_digest
        send_weekly_digest()


@celery.task(name="tasks.run_etl", bind=True, max_retries=1, default_retry_delay=600)
def run_etl_task(self):
    """Nightly warehouse load (services/etl.py). A data-quality failure raises
    so the run is retried once and logged loudly — bad numbers never land
    silently."""
    with _flask_context():
        from services.etl import run_pipeline
        try:
            return run_pipeline()
        except Exception as exc:
            raise self.retry(exc=exc)


# ── Dispatch helpers (what routes actually call) ──────────────────────────────

def _run_in_thread(task, args):
    """Pre-queue behavior: run the task function on a real OS thread, inside
    the current app's context, fully best-effort.

    `task.run` is already bound to the task instance, and for a task invoked
    directly (not by a worker) `self.retry(exc=...)` re-raises `exc` — so a
    failure here is logged once instead of retry-looping."""
    from flask import current_app
    try:
        app = current_app._get_current_object()
    except Exception:
        return

    def _job():
        with app.app_context():
            try:
                task.run(*args)
            except Exception:
                logger.exception("background task %s failed", task.name)

    try:
        import eventlet.patcher as _ep
        _thread_cls = _ep.original("threading").Thread
    except Exception:
        from threading import Thread as _thread_cls
    _thread_cls(target=_job, daemon=True).start()


def dispatch_push(user_id, title, body, url="/dashboard"):
    """Queue (or thread) a web-push delivery. Never raises."""
    try:
        if has_broker():
            send_push_task.delay(user_id, title, body, url)
        else:
            _run_in_thread(send_push_task, (user_id, title, body, url))
    except Exception:
        logger.exception("dispatch_push failed")


def dispatch_email(recipient, subject, body, is_html=False):
    """Queue (or thread) an email delivery. Never raises."""
    try:
        if has_broker():
            send_email_task.delay(recipient, subject, body, is_html)
        else:
            _run_in_thread(send_email_task, (recipient, subject, body, is_html))
    except Exception:
        logger.exception("dispatch_email failed")
