#!/bin/bash
echo "========================================"
echo "  GWAS Analysis Platform - Celery Worker"
echo "========================================"
echo ""

source venv/bin/activate

echo "Starting Celery worker..."
echo ""

celery -A celery_app.celery worker --loglevel=info --concurrency=4

