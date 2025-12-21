# apps/payments/apps.py
from django.apps import AppConfig
import logging


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"

    def ready(self):
        try:
            import apps.payments.receivers  # noqa
        except ImportError as e:
            logging.error(f"Failed to load payments receivers: {e}")
