"""
Django settings for quickdash project.
Production-ready with environment-based configuration.
"""

import logging
from pathlib import Path
import os
from decouple import config
from datetime import timedelta
from decimal import Decimal
import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SECURITY & CONFIGURATION
# ==========================================
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=True, cast=bool)
GOOGLE_CLIENT_ID = "857888499606-9f2b1vn2foqvmsq0hbonj8s9d7fae5db.apps.googleusercontent.com"

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost",
).split(",")


FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")


# Separate JWT signing key (can rotate independently)
JWT_SIGNING_KEY = config("JWT_SIGNING_KEY", default=SECRET_KEY)

# ==========================================
# APPLICATION DEFINITION
# ==========================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third Party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "django.contrib.gis",

    # Project Apps
    "apps.accounts",
    "apps.inventory",
    "apps.warehouse",
    "apps.orders",
    "apps.delivery",
    "apps.payments",
    "apps.notifications",
    "apps.analytics",
    "apps.catalog",
    "apps.utils",
    "apps.web_admin",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.warehouse.middleware.IdempotencyMiddleware",
    "apps.utils.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"
# WSGI_APPLICATION = "config.wsgi.application"

# ==========================================
# DATABASE
# ==========================================
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": config("DB_NAME", default="quickdash_db"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

DATABASE_URL = os.getenv("DATABASE_URL") or config("DATABASE_URL", default=None)
if DATABASE_URL:
    DATABASES["default"] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        engine="django.contrib.gis.db.backends.postgis"  # [ADD THIS] Engine explicitly pass karein
    )
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
# ==========================================
# REDIS / CACHE / CHANNELS / CELERY
# ==========================================
DEFAULT_REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{DEFAULT_REDIS_URL}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [f"{DEFAULT_REDIS_URL}/2"]},
    },
}

CELERY_BROKER_URL = f"{DEFAULT_REDIS_URL}/0"
CELERY_RESULT_BACKEND = f"{DEFAULT_REDIS_URL}/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CELERY_BEAT_SCHEDULE = {
    "run-daily-analytics": {
        "task": "apps.analytics.tasks.run_daily_analytics_for_date",
        "schedule": 60 * 60 * 24,  # daily
        "args": (),  # "today" by default
    },
    "orders-auto-cancel-every-5-mins": {
        "task": "auto_cancel_unpaid_orders",  # make sure Celery task name matches
        "schedule": crontab(minute="*/5"),
    },
}

# ==========================================
# AUTH / USER MODEL
# ==========================================
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==========================================
# I18N / TZ
# ==========================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# ==========================================
# STATIC & MEDIA
# ==========================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


STATICFILES_DIRS = [
    BASE_DIR / "static",
]



MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==========================================
# REST FRAMEWORK
# ==========================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",  # secure default
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.utils.throttle.BurstRateThrottle",
        "apps.utils.throttle.SustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "burst": "20/min",
        "sustained": "300/hour",
    },
}

# Browsable API only in DEBUG
if not DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
    ]

# ==========================================
# SIMPLE JWT
# ==========================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ==========================================
# CORS / CSRF
# ==========================================
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
).split(",")

CSRF_TRUSTED_ORIGINS = (
    config("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if config("CSRF_TRUSTED_ORIGINS", default="")
    else []
)

# ==========================================
# THIRD PARTY KEYS
# ==========================================
RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID", default=None)
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET", default=None)
RAZORPAY_WEBHOOK_SECRET = config("RAZORPAY_WEBHOOK_SECRET", default=None)

TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default=None)
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default=None)
TWILIO_FROM_NUMBER = config("TWILIO_FROM_NUMBER", default=None)

FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default=None)

# ==========================================
# BUSINESS CONSTANTS
# ==========================================
BASE_DELIVERY_FEE = config("BASE_DELIVERY_FEE", default="20.00", cast=Decimal)
FEE_PER_KM = config("FEE_PER_KM", default="5.00", cast=Decimal)
MIN_DELIVERY_FEE = config("MIN_DELIVERY_FEE", default="20.00", cast=Decimal)
MAX_DELIVERY_FEE = config("MAX_DELIVERY_FEE", default="100.00", cast=Decimal)
ORDER_CANCELLATION_WINDOW = config(
    "ORDER_CANCELLATION_WINDOW", default=300, cast=int
)
RIDER_BASE_FEE = config("RIDER_BASE_FEE", default="30.00", cast=Decimal)
AUTO_CANCEL_PENDING_MINUTES = config(
    "AUTO_CANCEL_PENDING_MINUTES", default=30, cast=int
)

# ==========================================
# IDEMPOTENCY SETTINGS
# ==========================================
IDEMPOTENCY_KEY_TTL = config("IDEMPOTENCY_KEY_TTL", default=30, cast=int)

# ==========================================
# GeoDjango
# ==========================================
if os.name == "posix":
    GDAL_LIBRARY_PATH = os.getenv(
        "GDAL_LIBRARY_PATH",
        "/usr/lib/x86_64-linux-gnu/libgdal.so",
    )

# ==========================================
# SECURITY HARDENING IN PRODUCTION
# ==========================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==========================================
# LOGGING
# ==========================================
logger = logging.getLogger(__name__)

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