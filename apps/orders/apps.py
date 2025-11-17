from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'

    # FIX: Yeh function add karein
    def ready(self):
        try:
            from . import signals  # Signals ko register karne ke liye
        except ImportError:
            pass