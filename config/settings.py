# config/settings.py
import logging
from pathlib import Path
import os
from decouple import config, Csv
from datetime import timedelta
from decimal import Decimal
import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SECURITY & CONFIGURATION
# ==========================================

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

# Hard Requirement for Production Secrets
JWT_SIGNING_KEY = config("JWT_SIGNING_KEY", default=None)

if not DEBUG:
    if not JWT_SIGNING_KEY or JWT_SIGNING_KEY == "unsafe-secret-key-change-in-prod":
        raise ImproperlyConfigured("Production requires a unique, secure JWT_SIGNING_KEY.")
    
    ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    # Trust the Nginx header for HTTPS detection
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    JWT_SIGNING_KEY = JWT_SIGNING_KEY or SECRET_KEY
    ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
    SECURE_SSL_REDIRECT = False

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
    "django.contrib.gis",
    "django.contrib.postgres",

    # Third Party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "drf_spectacular",
    "django_filters",

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "apps.utils.context_processors.google_maps_api_key",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"

# ==========================================
# DATABASE
# ==========================================
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
# REDIS / CELERY
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
CELERY_TASK_TIME_LIMIT = 1800

CELERY_BEAT_SCHEDULE = {
    "run-daily-analytics": {
        "task": "apps.analytics.tasks.run_daily_analytics_for_date",
        "schedule": crontab(hour=0, minute=5),
        "args": (),
    },
    "orders-auto-cancel": {
        # FIX: Fully qualified path to ensure Celery finds the task
        "task": "apps.orders.tasks.auto_cancel_unpaid_orders",
        "schedule": crontab(minute="*/5"),
    },
    "nightly-inventory-reconciliation": {
        "task": "apps.inventory.tasks.run_reconciliation",
        "schedule": crontab(hour=3, minute=0),
    },
}

# ==========================================
# AUTH
# ==========================================
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.SuperAdminBackend', # Prioritize Admin login
    'django.contrib.auth.backends.ModelBackend', # Fallback
]

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
TIME_ZONE = config("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# ==========================================
# STATIC & MEDIA
# ==========================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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
        "burst": "200/min",
        "sustained": "2000/hour",
        "anon": "100/min",
    },
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "apps.utils.pagination.StandardResultsSetPagination",
}

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
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'QuickDash API',
    'DESCRIPTION': 'E-commerce & Logistics API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ==========================================
# BUSINESS CONFIG
# ==========================================
RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID", default="rzp_test_placeholder")
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET", default="rzp_secret_placeholder")
RAZORPAY_WEBHOOK_SECRET = config("RAZORPAY_WEBHOOK_SECRET", default=None)

TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default=None)
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default=None)
TWILIO_FROM_NUMBER = config("TWILIO_FROM_NUMBER", default=None)

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default=None)

GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="fake-key")

BASE_DELIVERY_FEE = config("BASE_DELIVERY_FEE", default=20.00, cast=Decimal)
ORDER_CANCELLATION_WINDOW = config("ORDER_CANCELLATION_WINDOW", default=300, cast=int)
RIDER_BASE_FEE = config("RIDER_BASE_FEE", default=30.00, cast=Decimal)
IDEMPOTENCY_KEY_TTL = config("IDEMPOTENCY_KEY_TTL", default=30, cast=int)
RIDER_MAX_RADIUS_KM = config("RIDER_MAX_RADIUS_KM", default=10.0, cast=float)
DELIVERY_RADIUS_KM = config("DELIVERY_RADIUS_KM", default=5.0, cast=float)
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:8000")


# ==========================================
# EMAIL CONFIGURATION
# ==========================================
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# ==========================================
# FIREBASE CREDENTIALS
# ==========================================
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default=None)

# ==========================================
# LOGGING
# ==========================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
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
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": True,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": True,
        },
    },
}

if not DEBUG and SECRET_KEY == "unsafe-secret-key-change-in-prod":
    raise ImproperlyConfigured("Production requires a secure SECRET_KEY.")