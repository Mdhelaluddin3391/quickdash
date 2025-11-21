"""
Django settings for quickdash project.
Updated to match the 'Best' project standards.
"""

import logging
from pathlib import Path
import os
from decouple import config
from datetime import timedelta
from decimal import Decimal
import dj_database_url

# Load .env manually if needed (optional if using python-decouple correctly)
# from dotenv import load_dotenv
# load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SECURITY & CONFIGURATION
# ==========================================
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# Allowed Hosts ko environment se load karein
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')

# ==========================================
# APPLICATION DEFINITION
# ==========================================
INSTALLED_APPS = [
    # ASGI server (Daphne) is a runtime/deployment dependency and should not be in INSTALLED_APPS
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party
    'rest_framework',
    'rest_framework_simplejwt',
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    'django.contrib.gis',

    # My Apps (Apps folder structure maintain kiya hai)
    'apps.accounts',
    'apps.inventory',
    'apps.warehouse', # Isko 'wms' logic se update karna padega
    'apps.orders',
    'apps.delivery',
    'apps.payments',
    'apps.notifications',
    'apps.analytics',
    'apps.catalog',
    'apps.utils',
    # 'apps.store', # Agar store app hai toh uncomment karein
    # 'apps.dashboard', # Agar dashboard app add kiya hai toh
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware', # CORS sabse upar hona chahiye
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'apps.warehouse.middleware.IdempotencyMiddleware' # Optional
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Global templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'config.asgi.application'
# WSGI_APPLICATION = 'config.wsgi.application'

# --- Database Configuration ---
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis', # PostGIS use karein (Best practice)
        'NAME': config('DB_NAME', default='quickdash_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Allow parsing DATABASE_URL (useful for Docker and 12-factor deployments)
DATABASE_URL = os.getenv('DATABASE_URL') or config('DATABASE_URL', default=None)
if DATABASE_URL:
    # dj-database-url parses DATABASE_URL and returns a Django DATABASES config dict
    DATABASES['default'] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)

# --- Redis Configuration (Cache, Celery, Channels) ---
DEFAULT_REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379')

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{DEFAULT_REDIS_URL}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# Channels (WebSockets)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"{DEFAULT_REDIS_URL}/2"],
        },
    },
}

# Celery
CELERY_BROKER_URL = f"{DEFAULT_REDIS_URL}/0"
CELERY_RESULT_BACKEND = f"{DEFAULT_REDIS_URL}/0"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# --- Password & Auth ---
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = True

# --- Static & Media ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
}
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.utils.throttle.BurstRateThrottle",
        "apps.utils.throttle.SustainedRateThrottle",
    ]
}
MIDDLEWARE += [
    "apps.utils.middleware.RequestLogMiddleware",
]


CELERY_BEAT_SCHEDULE = {
    "run-daily-analytics": {
        "task": "apps.analytics.tasks.run_daily_analytics_for_date",
        "schedule": 60 * 60 * 24,  # daily
        "args": (),  # empty means "today"
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS Settings ---
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000').split(',')

# --- Third Party Keys ---
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default=None)
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default=None)
RAZORPAY_WEBHOOK_SECRET = config('RAZORPAY_WEBHOOK_SECRET', default=None)

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default=None)
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default=None)
TWILIO_FROM_NUMBER = config('TWILIO_FROM_NUMBER', default=None)

FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default=None)

# --- Business Logic Constants (Best Project Logic) ---
BASE_DELIVERY_FEE = config('BASE_DELIVERY_FEE', default='20.00', cast=Decimal)
FEE_PER_KM = config('FEE_PER_KM', default='5.00', cast=Decimal)
MIN_DELIVERY_FEE = config('MIN_DELIVERY_FEE', default='20.00', cast=Decimal)
MAX_DELIVERY_FEE = config('MAX_DELIVERY_FEE', default='100.00', cast=Decimal)
ORDER_CANCELLATION_WINDOW = config('ORDER_CANCELLATION_WINDOW', default=300, cast=int) # 5 mins
RIDER_BASE_FEE = config('RIDER_BASE_FEE', default='30.00', cast=Decimal)

# Orders auto-cancel window (minutes) — used by Celery task
AUTO_CANCEL_PENDING_MINUTES = config('AUTO_CANCEL_PENDING_MINUTES', default=30, cast=int)

# Celery beat schedule: run auto-cancel task every X minutes (configurable)
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = globals().get('CELERY_BEAT_SCHEDULE', {})
CELERY_BEAT_SCHEDULE.update({
    'orders-auto-cancel-every-5-mins': {
        'task': 'auto_cancel_unpaid_orders',
        'schedule': crontab(minute='*/5'),
    }
})

# GeoDjango (Linux path fix)
if os.name == 'posix':
    GDAL_LIBRARY_PATH = os.getenv('GDAL_LIBRARY_PATH', '/usr/lib/x86_64-linux-gnu/libgdal.so')

logger = logging.getLogger(__name__)

# Basic logging configuration (console). Can be extended per-environment.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "": {"handlers": ["console"], "level": "INFO"},
    },
}