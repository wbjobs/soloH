#!/bin/bash
echo "========================================"
echo "  GWAS Analysis Platform - Backend"
echo "========================================"
echo ""

echo "[1/4] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "[2/4] Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "[3/4] Copying environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
fi

echo ""
echo "[4/4] Starting Flask server..."
echo ""
echo "Starting GWAS API Server on http://localhost:5000"
echo ""
python app.py
