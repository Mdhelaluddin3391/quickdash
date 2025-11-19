from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        """
        App initialization ke waqt signals ko import karna zaroori hai,
        varna receivers work nahi karenge.
        """
        import apps.accounts.receivers