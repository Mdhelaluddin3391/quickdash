#!/bin/sh
set -e

# Define a lock directory for migrations
MIGRATION_LOCK_DIR="/tmp/django_migrations_lock"

echo "Waiting for DB..."
python << END
import sys, os, psycopg2, time

# Retry for 30 seconds
for i in range(30):
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "quickdash_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            host=os.getenv("DB_HOST", "db"),
            port=os.getenv("DB_PORT", "5432")
        )
        conn.close()
        print("DB Connection Successful.")
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for DB... ({i}/30) Error: {e}")
        time.sleep(1)

print("Could not connect to DB after 30 attempts.")
sys.exit(1)
END

# Only one container should run migrations.
echo "Running Migrations..."
python manage.py migrate --noinput

echo "Collecting Static..."
python manage.py collectstatic --noinput --clear

# Superuser check (Only in Dev/First Run)
if [ "$CREATE_SUPERUSER" = "true" ]; then
    python manage.py create_admin
fi

echo "Starting Daphne..."
# Use 0.0.0.0 for Docker networking
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application