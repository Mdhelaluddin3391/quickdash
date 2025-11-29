#!/bin/sh
set -e

# Fix ownership of static and media directories (Run as Root)
echo "Fixing permissions..."
mkdir -p /code/staticfiles /code/media
chown -R appuser:appgroup /code/staticfiles /code/media

# Wait for DB
python << END
import sys
import os
import psycopg2
import time

db_name = os.getenv("DB_NAME", "quickdash_db")
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASSWORD", "postgres")
db_host = os.getenv("DB_HOST", "db")
db_port = os.getenv("DB_PORT", "5432")

for i in range(30):
    try:
        conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
        conn.close()
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f"Waiting for DB... {i}")
        time.sleep(1)
sys.exit(1)
END

echo "DB Connected."

# Run Migrations (as appuser)
echo "Applying migrations..."
gosu appuser python manage.py migrate --noinput

# Collect Static (as appuser)
echo "Collecting static..."
gosu appuser python manage.py collectstatic --noinput

# Create Superuser if needed
if [ "$create_superuser" = "true" ]; then
    gosu appuser python manage.py create_admin
fi

echo "Starting Daphne..."
# Switch user to appuser and run daphne
exec gosu appuser daphne -b 0.0.0.0 -p 8000 config.asgi:application