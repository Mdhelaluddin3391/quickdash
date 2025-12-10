from django.apps import AppConfig
import logging

class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.warehouse'

    def ready(self):
        try:
            # FIX: Import receivers to ensure signal handlers are registered
            import apps.warehouse.receivers  # noqa
        except ImportError as e:
            logging.warning(f"Warehouse receivers could not be imported: {e}")