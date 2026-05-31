import os
from celery import Celery
from config import config

env = os.getenv('FLASK_ENV', 'default')
_config = config[env]

celery = Celery(
    'ancient_ocr',
    broker=_config.CELERY_BROKER_URL,
    backend=_config.CELERY_RESULT_BACKEND
)

celery.conf.update(_config.__dict__)
celery.conf.task_serializer = _config.CELERY_TASK_SERIALIZER
celery.conf.result_serializer = _config.CELERY_RESULT_SERIALIZER
celery.conf.accept_content = _config.CELERY_ACCEPT_CONTENT
celery.conf.timezone = _config.CELERY_TIMEZONE
celery.conf.task_track_started = _config.CELERY_TASK_TRACK_STARTED
celery.conf.task_time_limit = _config.CELERY_TASK_TIME_LIMIT

_flask_app = None


def get_flask_app():
    global _flask_app
    if _flask_app is None:
        from app import create_app
        _flask_app = create_app(_config)
    return _flask_app


TaskBase = celery.Task


class ContextTask(TaskBase):
    abstract = True
    
    def __call__(self, *args, **kwargs):
        app = get_flask_app()
        with app.app_context():
            return TaskBase.__call__(self, *args, **kwargs)


celery.Task = ContextTask

from tasks import processing_tasks

if __name__ == '__main__':
    celery.start()
