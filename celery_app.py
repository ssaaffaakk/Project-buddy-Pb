"""
Celery application (task queue).

With CELERY_BROKER_URL (or REDIS_URL) set, tasks are queued to Redis and run
on a worker with automatic retries:

    celery -A celery_worker.celery worker --beat --loglevel=info

Without a broker, services/tasks.py falls back to the pre-queue behavior
(background OS thread / inline call), so a broker-less deployment — like
Render's single free web service — keeps working unchanged.
"""

from celery import Celery

celery = Celery("projectbuddy")


def init_celery(app):
    """Bind broker config from the Flask app. Called by create_app()."""
    broker = app.config.get("CELERY_BROKER_URL") or None
    celery.conf.update(
        broker_url=broker,
        task_ignore_result=True,
        task_always_eager=broker is None,   # no broker → run inline
        broker_connection_retry_on_startup=True,
        # Periodic jobs (need `--beat` on the worker). The in-process hourly
        # thread in app.py stays as a fallback; the deadline check is
        # idempotent, so an occasional double run is harmless.
        beat_schedule={
            "deadline-check-hourly": {
                "task": "tasks.check_deadlines",
                "schedule": 3600.0,
            },
        },
    )
    return celery


def has_broker():
    return bool(celery.conf.broker_url)
