# apps/delivery/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.delivery'

    def ready(self):
        try:
            # [FIX] Explicit import to register signal handlers
            import apps.delivery.receivers
            logger.info("Delivery signals registered.")
        except ImportError as e:
            logger.error(f"Failed to import delivery receivers: {e}")