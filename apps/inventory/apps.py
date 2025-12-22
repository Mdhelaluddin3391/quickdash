# apps/inventory/apps.py
from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    verbose_name = "Inventory Management"

    def ready(self):
        # No implicit signals. 
        # Explicit service calls are preferred as per Architecture guidelines.
        pass