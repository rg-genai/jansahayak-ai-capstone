#!/usr/bin/env bash
# One-command local launcher for JanSahayak AI on macOS / Linux
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/python" ]; then
  echo "[ERROR] Python virtual environment (.venv) not found."
  echo "Run: python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "data/jansahayak.db" ] || [ ! -f "data/index/embeddings.npy" ]; then
  echo "[INFO] Hybrid index not found. Running data ingestion first (~9 mins)..."
  .venv/bin/python scripts/ingest_data.py --scope central
fi

# Stop any stale process on port 8000
if command -v lsof >/dev/null 2>&1; then
  STALE_PIDS=$(lsof -ti :8000 || true)
  if [ -n "$STALE_PIDS" ]; then
    echo "[INFO] Stopping stale backend process on port 8000..."
    kill -9 $STALE_PIDS || true
    sleep 1
  fi
fi

echo "[1/2] Starting JanSahayak AI FastAPI backend (single worker, port 8000)..."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "Stopping FastAPI backend (PID $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 25); do
  sleep 0.5
  if curl -sf http://127.0.0.1:8000/api/auth/personas >/dev/null 2>&1; then
    echo "[OK] Backend verified live on http://127.0.0.1:8000"
    break
  fi
done

echo "[2/2] Starting JanSahayak AI React + Vite frontend (port 5173)..."
echo "  Open App:     http://localhost:5173"
echo "  Backend API:  http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop both servers."
echo ""

cd frontend
npm run dev
