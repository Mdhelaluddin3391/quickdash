from django.apps import AppConfig
import logging

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        try:
            import apps.notifications.receivers  # noqa: F401
        except ImportError as e:
            logging.error(f"Failed to load notification receivers: {e}")