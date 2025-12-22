import random
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from .models import User, UserRole, Role, OTPLog

class AuthService:
    """
    Domain logic for Authentication and Identity Management.
    """
    
    @staticmethod
    def generate_otp(phone_number, purpose="LOGIN"):
        # Security: In production, use a more secure random source
        otp_code = str(random.randint(100000, 999999))
        expiry = timezone.now() + timedelta(minutes=5)
        
        # Invalidate old unused OTPs for this phone
        OTPLog.objects.filter(phone_number=phone_number, is_used=False).update(is_used=True)
        
        otp_log = OTPLog.objects.create(
            phone_number=phone_number,
            otp_code=otp_code,
            expires_at=expiry,
            purpose=purpose
        )
        
        # Integration point for SMS Gateway
        # send_sms_task.delay(phone_number, f"Your OTP is {otp_code}")
        
        return otp_log

    @staticmethod
    def verify_otp(phone_number, otp_code, role_requested):
        """
        Validates OTP and handles role-based account creation/check.
        """
        otp_entry = OTPLog.objects.filter(
            phone_number=phone_number,
            otp_code=otp_code,
            is_used=False
        ).last()

        if not otp_entry or not otp_entry.is_valid():
            return None, "Invalid or expired OTP"

        otp_entry.is_used = True
        otp_entry.save()

        # Get or Create Identity
        user, created = User.objects.get_or_create(phone_number=phone_number)
        
        # Check Role Permissions
        user_role, role_exists = UserRole.objects.get_or_create(user=user, role=role_requested)
        
        if role_requested in [Role.RIDER, Role.EMPLOYEE]:
            if not user_role.is_verified:
                return None, f"Unauthorized: {role_requested} account requires admin approval."

        return user, None

    @staticmethod
    def switch_role(user, target_role):
        """
        Ensures a user is switching to a role they actually possess.
        """
        has_role = UserRole.objects.filter(user=user, role=target_role).exists()
        if not has_role:
            raise ValueError(f"User does not have the {target_role} role.")
        return True