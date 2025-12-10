#!/bin/sh
set -e

# FIX: Use environment variables with defaults
HOST="${DB_HOST:-db}"
PORT="${DB_PORT:-5432}"
USER="${DB_USER:-postgres}"
PASSWORD="${DB_PASSWORD:-postgres}"
DB_NAME="${DB_NAME:-quickdash_db}"

echo "Waiting for postgres at $HOST:$PORT..."

# PGPASSWORD is used by psql/pg_isready
export PGPASSWORD="$PASSWORD"

# Try for 30 seconds
for i in $(seq 1 30); do
  if pg_isready -h "$HOST" -p "$PORT" -U "$USER" -d "$DB_NAME"; then
    echo "Database $DB_NAME is ready!"
    exec "$@"
  fi
  echo "Waiting for database... ($i/30)"
  sleep 1
done

echo "Database connection failed after 30 seconds."
exit 1