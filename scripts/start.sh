#!/usr/bin/env bash
# Start Pramaan AI for development:
#   backend  (FastAPI)  -> http://localhost:8000
#   frontend (Vite)     -> http://localhost:5173   <- open this in your browser
# Press Ctrl+C once to stop both.
#
# The AI model (llama-server on port 8081) is started separately; see README.md.

set -euo pipefail

# Go to the project root (the folder above scripts/), whatever folder we were started from.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# --- checks, with friendly messages ---
if [ ! -f ".env" ]; then
  echo "No .env file found. Create one with:  cp .env.example .env"
  exit 1
fi
if [ ! -x "backend/.venv/bin/uvicorn" ]; then
  echo "Backend is not installed. Run:"
  echo "  cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
if [ ! -d "frontend/node_modules" ]; then
  echo "Frontend is not installed. Run:  cd frontend && npm install"
  exit 1
fi

# When this script exits (Ctrl+C or an error), stop both servers.
cleanup() {
  echo ""
  echo "Stopping Pramaan AI..."
  kill ${BACKEND_PID:-} ${FRONTEND_PID:-} 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM

echo "Starting backend on http://localhost:8000 ..."
(cd backend && exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
(cd frontend && exec ./node_modules/.bin/vite --port 5173) &
FRONTEND_PID=$!

echo ""
echo "Pramaan AI is starting. Open http://localhost:5173 in your browser."
echo "Press Ctrl+C to stop."

# Keep running until either server stops (macOS bash 3.2 has no "wait -n", so check every second).
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
echo "One of the servers stopped. Check the messages above."
