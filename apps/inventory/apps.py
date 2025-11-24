# apps/inventory/apps.py
from django.apps import AppConfig
import logging

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'

    def ready(self):
        try:
            import apps.inventory.receivers 
        except ImportError as e:
            logging.error(f"Failed to load inventory receivers: {e}")