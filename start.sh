#!/bin/sh
set -e

# Define a lock file for migrations to prevent race conditions in horizontal scaling
MIGRATION_LOCK_FILE="/tmp/django_migrations.lock"

echo "Waiting for Services (DB & Redis)..."
python << END
import sys, os, psycopg2, redis, time

db_host = os.getenv("DB_HOST", "db")
db_port = os.getenv("DB_PORT", "5432")
redis_url = os.getenv("REDIS_URL", "redis://redis:6379")

# Retry loop
for i in range(30):
    db_ready = False
    redis_ready = False
    
    # Check DB
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "quickdash_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            host=db_host,
            port=db_port
        )
        conn.close()
        db_ready = True
    except Exception as e:
        print(f"Waiting for DB... {e}")

    # Check Redis
    try:
        r = redis.from_url(redis_url)
        r.ping()
        redis_ready = True
    except Exception as e:
        print(f"Waiting for Redis... {e}")

    if db_ready and redis_ready:
        print("All Services Ready.")
        sys.exit(0)
    
    time.sleep(1)

print("Services failed to become ready.")
sys.exit(1)
END

# MIGRATION LOCKING: Only one instance should run migrations
echo "Acquiring migration lock..."
python << END
import sys, fcntl, time, os
lock_file = "$MIGRATION_LOCK_FILE"
f = open(lock_file, 'w')
try:
    # Exclusive non-blocking lock
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("Lock acquired. Running migrations...")
    os.system("python manage.py migrate --noinput")
    print("Migrations complete.")
except BlockingIOError:
    print("Another instance is running migrations. Waiting...")
    # Wait for lock to be released
    fcntl.flock(f, fcntl.LOCK_EX)
    print("Lock released. Proceeding.")
finally:
    f.close()
END

echo "Collecting Static..."
python manage.py collectstatic --noinput --clear

# Superuser check (Only in Dev/First Run)
if [ "$CREATE_SUPERUSER" = "true" ]; then
    python manage.py create_admin
fi

echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application