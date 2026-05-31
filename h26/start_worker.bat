@echo off
echo Starting Celery Worker...

set PYTHONPATH=%cd%
set C_FORCE_ROOT=1

echo.
echo Checking environment...
if not exist ".env" (
    echo Warning: .env file not found, using default settings
)

echo.
echo Starting Celery worker with concurrency 2...
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2 -P solo

pause
