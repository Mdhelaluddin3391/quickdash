# apps/analytics/apps.py
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"

    def ready(self):
        # future: import signals if needed
        try:
            import apps.analytics.receivers  # noqa
        except ImportError:
            pass
