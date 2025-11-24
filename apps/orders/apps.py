from django.apps import AppConfig
import logging

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'

    def ready(self):
        try:
            import apps.orders.receivers  # noqa: F401
        except ImportError as e:
            logging.error(f"Failed to load orders receivers: {e}")   