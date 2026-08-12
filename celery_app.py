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
from celery.schedules import crontab

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
            # Nightly warehouse load (03:00 UTC — off-peak for a EU campus)
            "etl-nightly": {
                "task": "tasks.run_etl",
                "schedule": crontab(hour=3, minute=0),
            },
            # Daily model drift check against the training feature snapshot
            "drift-check-daily": {
                "task": "tasks.check_model_drift",
                "schedule": crontab(hour=5, minute=0),
            },
            # Weekly retrain on accumulated interaction data (Sunday 04:00 UTC)
            "retrain-weekly": {
                "task": "tasks.retrain_recommender",
                "schedule": crontab(day_of_week=0, hour=4, minute=0),
            },
            # Weekly recommendation digest (Monday 08:00 UTC — start of the week)
            "digest-weekly": {
                "task": "tasks.send_weekly_digest",
                "schedule": crontab(day_of_week=1, hour=8, minute=0),
            },
            "purge-expired-demos": {
                "task": "tasks.purge_expired_demos",
                "schedule": 3600.0,
            },
        },
    )
    return celery


def has_broker():
    return bool(celery.conf.broker_url)
