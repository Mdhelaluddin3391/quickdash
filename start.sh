echo "Acquiring distributed migration lock..."
python << END
import sys, os, time, redis

# Configuration
redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
lock_key = "django_migration_lock"
lock_timeout = 300  # 5 minutes max for migration
poll_interval = 2

try:
    r = redis.from_url(redis_url)
    
    # Try to acquire lock
    # set(name, value, ex=seconds, nx=True) -> returns True if key was set (lock acquired)
    acquired = r.set(lock_key, "locked", ex=lock_timeout, nx=True)
    
    if acquired:
        print("Lock acquired. Running migrations...")
        exit_code = os.system("python manage.py migrate --noinput")
        r.delete(lock_key) # Release lock
        if exit_code != 0:
            print("Migration failed!")
            sys.exit(exit_code)
        print("Migrations complete.")
    else:
        print("Another instance is migrating. Waiting...")
        # Wait until lock is released
        while r.get(lock_key):
            time.sleep(poll_interval)
        print("Lock released. Proceeding.")

except Exception as e:
    print(f"Redis Lock Error: {e}")
    # Fallback: Just try to run migrate if Redis fails (Riskier but better than hanging)
    os.system("python manage.py migrate --noinput")
END