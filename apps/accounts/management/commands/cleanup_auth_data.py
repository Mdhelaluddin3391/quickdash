from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import PhoneOTP, UserSession


class Command(BaseCommand):
    help = "Cleanup old OTPs and inactive sessions"

    def handle(self, *args, **options):
        now = timezone.now()
        # delete OTP older than 1 hour
        otp_threshold = now - timedelta(hours=1)
        deleted_otps, _ = PhoneOTP.objects.filter(created_at__lt=otp_threshold).delete()

        # delete sessions older than 30 days (both active/inactive)
        session_threshold = now - timedelta(days=30)
        deleted_sessions, _ = UserSession.objects.filter(
            created_at__lt=session_threshold
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_otps} OTPs and {deleted_sessions} sessions."
            )
        )
