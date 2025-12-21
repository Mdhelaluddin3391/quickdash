#!/bin/sh
set -e

# Use environment variables with defaults matching docker-compose
HOST="${DB_HOST:-db}"
PORT="${DB_PORT:-5432}"
USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-quickdash_db}"
# PGPASSWORD is handled automatically by psql if exported
export PGPASSWORD="${DB_PASSWORD:-postgres}"

echo "Waiting for postgres at $HOST:$PORT..."

# Try for 45 seconds (slightly increased)
for i in $(seq 1 45); do
  if pg_isready -h "$HOST" -p "$PORT" -U "$USER" -d "$DB_NAME"; then
    echo "Database $DB_NAME is ready!"
    exec "$@"
  fi
  echo "Waiting for database... ($i/45)"
  sleep 1
done

echo "Database connection failed after 45 seconds."
exit 1