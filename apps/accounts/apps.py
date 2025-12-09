from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        # FIX: Explicitly import receivers to register signals on startup.
        # Without this, the @receiver decorators in receivers.py are never executed.
        import apps.accounts.receivers
