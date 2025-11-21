from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        """
        App init pe receivers import karna jaruri hai
        (customer profile / flags auto create ke liye).
        """
        from . import receivers  # noqa
