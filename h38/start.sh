#!/bin/bash
echo "Starting CRISPR Off-Target Predictor..."

if [ ! -f .env ]; then
    echo "Warning: .env file not found, using default settings"
fi

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Starting server on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""

python main.py
