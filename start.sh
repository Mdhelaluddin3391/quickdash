#!/bin/bash
set -e

# Configuration
# Default to standard Redis port if not set
export REDIS_URL="${REDIS_URL:-redis://redis:6379}"

echo "Starting deployment process..."

# 1. Distributed Migration Lock
# This prevents race conditions when running multiple replicas
python << END
import sys, os, time, redis

redis_url = os.getenv("REDIS_URL")
lock_key = "django_migration_lock"
lock_timeout = 300
poll_interval = 2

try:
    r = redis.from_url(redis_url)
    acquired = r.set(lock_key, "locked", ex=lock_timeout, nx=True)
    
    if acquired:
        print("Lock acquired. Running migrations...")
        exit_code = os.system("python manage.py migrate --noinput")
        r.delete(lock_key)
        if exit_code != 0:
            sys.exit(exit_code)
        print("Migrations complete.")
    else:
        print("Another instance is migrating. Waiting...")
        while r.get(lock_key):
            time.sleep(poll_interval)
        print("Lock released. Proceeding.")

except Exception as e:
    print(f"Redis Lock Error: {e}")
    # Fallback: Try to run migrate anyway if Redis fails
    os.system("python manage.py migrate --noinput")
END

# 2. Collect Static Files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 3. Start Application Server
# Using Gunicorn with Uvicorn workers for ASGI (Channels) support
# exec replaces the shell process with Gunicorn
echo "Starting Gunicorn (ASGI)..."
exec gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --chdir /code \
    --workers 3 \
    --access-logfile - \
    --error-logfile -