@echo off
echo Starting Protein Contact Map Prediction API Server...

set PYTHONPATH=%cd%
set APP_ENV=development

echo.
echo Checking environment...
if not exist ".env" (
    echo Warning: .env file not found, using default settings
    copy .env.example .env
)

echo.
echo Starting Uvicorn server on http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
