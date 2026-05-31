import os
from celery import Celery
from flask import Flask
import sys

def make_celery(app=None):
    if app is None:
        app = Flask(__name__)
        from config import Config
        app.config.from_object(Config)
    
    celery = Celery(
        app.import_name,
        broker=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600 * 24,
        task_soft_time_limit=3600 * 23,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    return celery
