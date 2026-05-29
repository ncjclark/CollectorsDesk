#!/bin/bash
# Start ResellResearch — runs backend and frontend, then opens the browser

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting ResellResearch..."

# Backend
cd "$ROOT/backend"
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "✓ Backend started (PID $BACKEND_PID) → http://localhost:8000"

# Frontend
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
echo "✓ Frontend started (PID $FRONTEND_PID) → http://localhost:5173"

# Give servers a moment to bind, then open browser
sleep 2
open http://localhost:5173

echo ""
echo "App running at http://localhost:5173"
echo "Press Ctrl+C to stop both servers."
echo ""

# Save PIDs for stop.sh
echo "$BACKEND_PID $FRONTEND_PID" > "$ROOT/.pids"

# Wait — keep script alive so Ctrl+C kills children
wait $BACKEND_PID $FRONTEND_PID
