#!/bin/bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$ROOT/.pids"

if [ -f "$PIDFILE" ]; then
  read -r BACKEND_PID FRONTEND_PID < "$PIDFILE"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  rm "$PIDFILE"
  echo "Stopped backend ($BACKEND_PID) and frontend ($FRONTEND_PID)."
else
  echo "No .pids file found — killing by port..."
  lsof -ti:8000 | xargs kill -9 2>/dev/null
  lsof -ti:5173 | xargs kill -9 2>/dev/null
  echo "Done."
fi
