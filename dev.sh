#!/bin/bash
# Run both API and Web dev servers

trap 'kill 0' EXIT

echo "Starting API on http://localhost:8000"
cd "$(dirname "$0")"
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

echo "Starting Web on http://localhost:3000"
cd web
npm run dev &
WEB_PID=$!

echo ""
echo "  API:  http://localhost:8000/docs"
echo "  Web:  http://localhost:3000"
echo ""

wait
