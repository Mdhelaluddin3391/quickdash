import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Create an admin user safely via Environment Variables."

    def handle(self, *args, **options):
        # 1. Safety Check for Production
        if not settings.DEBUG and not os.getenv("ALLOW_CREATE_ADMIN_IN_PROD") == "True":
            self.stderr.write(self.style.ERROR(
                "Production Lock: Set ALLOW_CREATE_ADMIN_IN_PROD=True to run this."
            ))
            return

        phone = os.getenv("ADMIN_PHONE")
        password = os.getenv("ADMIN_PASSWORD")

        if not phone or not password:
            self.stderr.write(self.style.ERROR(
                "Missing ADMIN_PHONE or ADMIN_PASSWORD env vars."
            ))
            return

        User = get_user_model()

        # 2. Get or Create
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={"role": "ADMIN", "is_active": True}
        )

        # 3. Enforce Permissions
        user.is_staff = True
        user.is_superuser = True
        user.role = "ADMIN"
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Superuser: {phone}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated Superuser: {phone}"))