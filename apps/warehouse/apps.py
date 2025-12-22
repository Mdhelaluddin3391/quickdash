from django.apps import AppConfig

class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.warehouse'
    verbose_name = 'Warehouse Management System'

    def ready(self):
        # Register signals if any (avoiding logic in signals as requested)
        pass