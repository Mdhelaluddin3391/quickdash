# apps/delivery/apps.py

from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.delivery"

    def ready(self):
        # ❌ No signals
        pass
