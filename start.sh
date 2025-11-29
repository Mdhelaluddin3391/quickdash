#!/bin/sh
set -e

# Wait for DB (Uses python snippet instead of netcat for portability)
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

# Only migrate in explicit deployment tasks, or careful dev envs.
# For simplicity in this setup, we keep it, but in high-scale, this runs in a separate job.
echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static..."
python manage.py collectstatic --noinput

if [ "$create_superuser" = "true" ]; then
    python manage.py create_admin
fi

echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application