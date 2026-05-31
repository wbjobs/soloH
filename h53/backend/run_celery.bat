@echo off
echo ========================================
echo   GWAS Analysis Platform - Celery Worker
echo ========================================
echo.

call venv\Scripts\activate

echo Starting Celery worker...
echo.

celery -A celery_app.celery worker --loglevel=info --pool=solo --concurrency=2

pause
