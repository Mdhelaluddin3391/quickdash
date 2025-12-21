# apps/accounts/management/commands/create_admin.py
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.conf import settings



class Command(BaseCommand):
    help = "Create an admin user using env vars (safe for dev)."

    def handle(self, *args, **options):
        # 🔐 Safety check – prod me default se mat chalana
        if not settings.DEBUG and not os.getenv("ALLOW_CREATE_ADMIN_IN_PROD"):
            self.stderr.write(
                self.style.ERROR(
                    "Refusing to create admin because DEBUG=False and "
                    "ALLOW_CREATE_ADMIN_IN_PROD is not set."
                )
            )
            return

        phone = os.getenv("ADMIN_PHONE")
        password = os.getenv("ADMIN_PASSWORD")

        if not phone or not password:
            self.stderr.write(
                self.style.ERROR(
                    "ADMIN_PHONE and ADMIN_PASSWORD env vars are required."
                )
            )
            return

        User = get_user_model()

        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={"is_staff": True, "is_superuser": True},
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created new admin: {phone}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"Admin {phone} already exists, updating password/flags")
            )
            user.is_staff = True
            user.is_superuser = True

        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"Admin {phone} is ready."))
