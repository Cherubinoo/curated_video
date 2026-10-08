#!/bin/sh
set -e

echo "[entrypoint] running database migrations..."
alembic upgrade head

echo "[entrypoint] starting API server..."
exec uvicorn app.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}"
