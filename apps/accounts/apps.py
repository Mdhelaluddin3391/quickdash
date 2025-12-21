from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        # Ensure signals/receivers are imported on startup
        try:
            import apps.accounts.receivers  # noqa: F401
        except Exception:
            # Avoid failing app startup if receivers import has issues; log instead
            import logging
            logging.getLogger(__name__).exception("Failed to import apps.accounts.receivers")
