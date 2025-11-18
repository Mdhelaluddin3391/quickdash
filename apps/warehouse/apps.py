from django.apps import AppConfig
import logging

class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.warehouse'
    verbose_name = 'Warehouse / WMS'

    def ready(self):
        try:
            import apps.warehouse.receivers  # noqa: F401
        except ImportError as e:
            logging.error(f"Failed to import warehouse receivers: {e}")