# apps/delivery/apps.py

from django.apps import AppConfig

class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.delivery'

    # --- FIX: YEH NAYA FUNCTION ADD KAREIN ---
    def ready(self):
        try:
            from . import signals  # Signals ko register karne ke liye import karein
        except ImportError:
            pass