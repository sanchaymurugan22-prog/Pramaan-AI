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

# --- free ports 8000 and 5173 ---
# An old Pramaan AI (for example from a terminal that was closed without Ctrl+C) may still be using
# them. Only OUR OWN servers are stopped: a uvicorn / vite (python / node) process running from this
# project's backend/ or frontend/ folder. Anything else on the port is left alone, and we stop here.
free_port() {
  local port=$1 pids pid cwd command
  pids=$(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  [ -z "$pids" ] && return 0
  # First look at every process on the port; stop only if ALL of them are ours.
  for pid in $pids; do
    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' || true)
    command=$(ps -o command= -p "$pid" 2>/dev/null || true)
    if { [ "$cwd" != "$ROOT/backend" ] && [ "$cwd" != "$ROOT/frontend" ]; } ||
       ! echo "$command" | grep -qiE 'uvicorn|vite|python|node'; then  # -i: macOS shows "Python"
      echo "Port $port is used by another program, not Pramaan AI:"
      echo "  process $pid: ${command:-unknown}"
      echo "Close that program (or run: kill $pid), then start again."
      exit 1
    fi
  done
  echo "Port $port is used by an old Pramaan AI server (process $(echo $pids)). Stopping it..."
  kill $pids 2>/dev/null || true
  # Wait up to 5 seconds for the port to become free; force-stop it if it is still there.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lsof -nP -t -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.5
  done
  echo "It did not stop in time; forcing it."
  kill -9 $pids 2>/dev/null || true
  sleep 0.5
}
free_port 8000
free_port 5173

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
(cd frontend && exec ./node_modules/.bin/vite --port 5173 --strictPort) &
FRONTEND_PID=$!

echo ""
echo "Pramaan AI is starting. Open http://localhost:5173 in your browser."
echo "Press Ctrl+C to stop."

# Keep running until either server stops (macOS bash 3.2 has no "wait -n", so check every second).
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
echo "One of the servers stopped. Check the messages above."
