from celery import Celery
from celery.schedules import crontab

from app.config import settings


def make_celery() -> Celery:
    celery = Celery(
        "protein_contact_prediction",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND
    )

    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,
        task_soft_time_limit=3300,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        result_expires=86400,
    )

    celery.conf.beat_schedule = {
        "cleanup-old-tasks-every-day": {
            "task": "app.tasks.celery_tasks.cleanup_old_tasks",
            "schedule": crontab(hour=2, minute=0),
        },
    }

    return celery
