#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — add your ANTHROPIC_API_KEY"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r backend/requirements.txt

echo ""
echo "Starting AD SelfIntegrator at http://localhost:8000"
echo ""

cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
