from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.delivery'

    def ready(self):
       
        import apps.delivery.receivers
        logger.info("Delivery signals registered successfully.")