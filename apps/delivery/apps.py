from django.apps import AppConfig
import logging

class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.delivery'

    def ready(self):
        try:
            import apps.delivery.receivers  
        except ImportError as e:
            logging.error(f"Failed to import delivery receivers: {e}")