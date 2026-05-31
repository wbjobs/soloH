@echo off
echo Starting CRISPR Off-Target Predictor...

if not exist .env (
    echo Warning: .env file not found, using default settings
)

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting server on http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.

python main.py
