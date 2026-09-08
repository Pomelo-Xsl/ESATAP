#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/uvicorn app.main:app --host "${SSD_PLATFORM_HOST:-0.0.0.0}" --port "${SSD_PLATFORM_PORT:-8000}"

