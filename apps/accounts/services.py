import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError, Throttled

from .models import User, OTP, Role
from .tasks import send_sms_task

class AuthService:
    
    OTP_EXPIRY_MINUTES = 5
    MAX_OTP_REQUESTS_WINDOW = 10  # minutes
    MAX_OTP_REQUESTS_LIMIT = 3
    MAX_OTP_ATTEMPTS = 3

    @staticmethod
    def request_otp(phone: str, role: str) -> str:
        """
        Generates a crypto-secure OTP with rate limiting.
        """
        # 1. Throttling: Prevent SMS Pumping
        cutoff = timezone.now() - timedelta(minutes=AuthService.MAX_OTP_REQUESTS_WINDOW)
        recent_count = OTP.objects.filter(
            phone=phone, 
            created_at__gte=cutoff
        ).count()

        if recent_count >= AuthService.MAX_OTP_REQUESTS_LIMIT:
            raise Throttled(detail="Too many OTP requests. Please try again later.")

        # 2. Generate Code
        # crypto-secure random 6 digits
        code = str(secrets.SystemRandom().randint(100000, 999999))
        
        # 3. Create Record
        OTP.objects.create(
            phone=phone,
            code=code,
            role=role,
            expires_at=timezone.now() + timedelta(minutes=AuthService.OTP_EXPIRY_MINUTES)
        )
        
        # 4. Async Side Effect: Send SMS
        # In Prod, this MUST rely on Celery.
        if settings.DEBUG:
            print(f"DEBUG OTP for {phone}: {code}")
        else:
            send_sms_task.delay(phone, code, role)
        
        return code

    @staticmethod
    @transaction.atomic
    def verify_otp_and_login(phone: str, code: str, role: str):
        """
        Verifies OTP, creates/retrieves user, and generates tokens.
        """
        # 1. Fetch valid OTP
        try:
            otp = OTP.objects.filter(
                phone=phone,
                role=role,
                is_verified=False
            ).latest('created_at')
        except OTP.DoesNotExist:
            raise ValidationError("Invalid or expired OTP.")

        # 2. Validation
        if otp.is_expired:
            raise ValidationError("OTP has expired.")
        
        if otp.code != code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            if otp.attempts >= AuthService.MAX_OTP_ATTEMPTS:
                raise ValidationError("Too many incorrect attempts. Request a new OTP.")
            raise ValidationError("Incorrect OTP.")

        # 3. Mark Verified (Prevent Replay)
        otp.is_verified = True
        otp.save(update_fields=['is_verified'])

        # 4. Get or Create User
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={'role': role, 'is_active': True}
        )

        # 5. Handle Profile Creation (Idempotent)
        if created or not AuthService._has_profile(user, role):
            AuthService._create_profile_for_role(user, role)

        # 6. Generate Tokens
        refresh = RefreshToken.for_user(user)
        refresh['role'] = role 

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user,
            'is_new': created
        }

    @staticmethod
    def _has_profile(user, role):
        if role == Role.CUSTOMER:
            return hasattr(user, 'customer_profile')
        elif role == Role.RIDER:
            return hasattr(user, 'rider_profile')
        return True # Employees/Admins managed manually

    @staticmethod
    def _create_profile_for_role(user, role):
        if role == Role.CUSTOMER:
            from apps.customers.services import CustomerService
            CustomerService.get_or_create_profile(user)
        elif role == Role.RIDER:
            from apps.riders.services import RiderService
            RiderService.create_pending_profile(user)