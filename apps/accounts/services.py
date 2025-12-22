import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError

from .models import User, OTP, Role
from .tasks import send_sms_task

class AuthService:
    
    @staticmethod
    def request_otp(phone: str, role: str) -> str:
        """
        Generates a crypto-secure OTP and schedules SMS.
        """
        # 1. Throttling/Security Check (Optional: Check recent OTPs)
        
        # 2. Generate Code
        code = str(secrets.SystemRandom().randint(100000, 999999))
        
        # 3. Create Record
        otp = OTP.objects.create(
            phone=phone,
            code=code,
            role=role,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        # 4. Async Side Effect: Send SMS
        if not settings.DEBUG:
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
        if otp.is_expired():
            raise ValidationError("OTP has expired.")
        
        if otp.code != code:
            otp.attempts += 1
            otp.save()
            if otp.attempts >= 3:
                raise ValidationError("Too many incorrect attempts. Request a new OTP.")
            raise ValidationError("Incorrect OTP.")

        # 3. Mark Verified
        otp.is_verified = True
        otp.save()

        # 4. Get or Create User
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={'role': role, 'is_active': True}
        )

        # 5. EXPLICIT LOGIC: Handle Profile Creation
        # Instead of a signal, we call the service directly.
        if created or not AuthService._has_profile(user, role):
            AuthService._create_profile_for_role(user, role)

        # 6. Generate Tokens
        refresh = RefreshToken.for_user(user)
        refresh['role'] = role # Custom claim

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
        """
        Routes profile creation to the correct domain app.
        """
        if role == Role.CUSTOMER:
            from apps.customers.services import CustomerService
            CustomerService.get_or_create_profile(user)
        elif role == Role.RIDER:
            from apps.riders.services import RiderService
            # Riders might need approval, so we might just create a pending profile
            RiderService.create_pending_profile(user)