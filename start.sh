#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

echo "Waiting for DB..."
/wait-for-db.sh

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Applying migrations..."
python manage.py migrate --noinput

# Create default admin if env vars exist (safe per your code logic)
python manage.py create_admin

echo "Starting Daphne Server..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application