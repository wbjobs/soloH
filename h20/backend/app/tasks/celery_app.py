from celery import Celery

from app.core.config import settings
from app.tasks.base_task import BaseTask

celery_app = Celery(
    "btc_analysis_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600 * 24,
    task_track_started=True,
    task_time_limit=3600 * 4,
    task_soft_time_limit=3600 * 3,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_default_queue="default",
    task_routes={
        "app.tasks.import_tasks.*": {"queue": "import"},
        "app.tasks.analysis_tasks.*": {"queue": "analysis"},
    },
    task_default_retry_delay=30,
    task_max_retries=3,
)

celery_app.Task = BaseTask

celery_app.autodiscover_tasks(["app.tasks"], force=True)

from app.tasks import import_tasks, analysis_tasks

__all__ = ["celery_app"]
