"""
Django settings for quickdash project.
Production-ready configuration with hardened security.
"""

import logging
from pathlib import Path
import os
from decouple import config, Csv
from datetime import timedelta
from decimal import Decimal
import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SECURITY & CONFIGURATION
# ==========================================
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

# Security: In production, ALLOWED_HOSTS must be explicit.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
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
    "django.contrib.gis",  # PostGIS support

    # Third Party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "drf_spectacular", # API Documentation

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
    # Custom Middleware
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

# ==========================================
# DATABASE (PostGIS)
# ==========================================
# Fix: Ensure logic correctly handles boolean cast for SSL
DB_SSL_REQUIRE = config("DB_SSL_REQUIRE", default=not DEBUG, cast=bool)

DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default="postgis://postgres:postgres@db:5432/quickdash_db"),
        conn_max_age=600,
        ssl_require=DB_SSL_REQUIRE
    )
}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# ==========================================
# REDIS / CACHE / CHANNELS / CELERY
# ==========================================
DEFAULT_REDIS_URL = config("REDIS_URL", default="redis://redis:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{DEFAULT_REDIS_URL}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
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
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800  # 30 mins

CELERY_BEAT_SCHEDULE = {
    "run-daily-analytics": {
        "task": "apps.analytics.tasks.run_daily_analytics_for_date",
        "schedule": crontab(hour=0, minute=5),
        "args": (),
    },
    "orders-auto-cancel": {
        "task": "auto_cancel_unpaid_orders",
        "schedule": crontab(minute="*/5"),
    },
    "nightly-inventory-reconciliation": {
        "task": "apps.inventory.tasks.run_reconciliation",
        "schedule": crontab(hour=3, minute=0),
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
STATICFILES_DIRS = [BASE_DIR / "static"]

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
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.utils.throttle.BurstRateThrottle",
        "apps.utils.throttle.SustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "burst": "60/min",
        "sustained": "1000/hour",
    },
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

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
# API DOCUMENTATION (Spectacular)
# ==========================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'QuickDash API',
    'DESCRIPTION': 'E-commerce & Logistics API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ==========================================
# BUSINESS KEYS
# ==========================================
RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID", default=None)
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET", default=None)
RAZORPAY_WEBHOOK_SECRET = config("RAZORPAY_WEBHOOK_SECRET", default=None)

TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default=None)
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default=None)
TWILIO_FROM_NUMBER = config("TWILIO_FROM_NUMBER", default=None)

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default=None)

# ==========================================
# BUSINESS LOGIC CONSTANTS
# ==========================================
BASE_DELIVERY_FEE = config("BASE_DELIVERY_FEE", default=20.00, cast=Decimal)
ORDER_CANCELLATION_WINDOW = config("ORDER_CANCELLATION_WINDOW", default=300, cast=int)
RIDER_BASE_FEE = config("RIDER_BASE_FEE", default=30.00, cast=Decimal)
IDEMPOTENCY_KEY_TTL = config("IDEMPOTENCY_KEY_TTL", default=30, cast=int)
RIDER_MAX_RADIUS_KM = config("RIDER_MAX_RADIUS_KM", default=10.0, cast=float)

# ==========================================
# LOGGING
# ==========================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": True},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": True},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": True},
    },
}

# ==========================================
# PRODUCTION SECURITY HARDENING
# ==========================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")