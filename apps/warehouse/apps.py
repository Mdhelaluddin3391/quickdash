# apps/warehouse/apps.py
from django.apps import AppConfig

class WarehouseConfig(AppConfig):
    name = 'apps.warehouse'
    verbose_name = 'Warehouse / WMS'

    def ready(self):
        # import signals to register receivers
        try:
            from . import signals  # noqa: F401
        except Exception:
            # don't crash app import if signals fail (log in prod)
            import logging
            logging.exception("Failed to import warehouse.signals")
