from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.payments'

    def ready(self):
        # Signal receivers for side-effects (e.g. sending email receipt)
        # Note: Core money logic is in services.py, not signals.
        import apps.payments.receivers