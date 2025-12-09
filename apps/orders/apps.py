from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'

    def ready(self):
        # FIX: Explicitly import receivers to register signals on startup.
        import apps.orders.receivers