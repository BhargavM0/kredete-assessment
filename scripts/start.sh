#!/usr/bin/env bash
set -euo pipefail

# Start the API and the static frontend server. Runs both in background for quick demos.
uvicorn src.api_placeholder:app --host 0.0.0.0 --port 8000 &

cd frontend
python -m http.server 8001 &

wait
