from django.apps import AppConfig
import logging

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'

    def ready(self):
        import apps.orders.receivers
        try:
            import apps.orders.receivers 
        except ImportError as e:
            logging.error(f"Failed to load orders receivers: {e}")   