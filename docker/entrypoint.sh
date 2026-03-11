#!/bin/bash
set -e

echo "==> Running database migrations..."
alembic upgrade head

echo "==> Creating default admin user..."
python scripts/init_admin.py || echo "[entrypoint] init_admin skipped or failed (non-fatal)"

echo "==> Starting application..."
exec "$@"
