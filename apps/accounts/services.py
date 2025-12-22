import secrets
from django.utils import timezone
from django.conf import settings
from .models import User, OTP
from .tasks import send_sms_task

class AuthService:
    
    @staticmethod
    def generate_otp(phone_number):
        # CRITICAL FIX: Use secrets for cryptographically strong random numbers
        otp_code = str(secrets.SystemRandom().randint(100000, 999999))
        
        # Invalidate old OTPs
        OTP.objects.filter(phone_number=phone_number, is_verified=False).delete()
        
        otp = OTP.objects.create(
            phone_number=phone_number,
            code=otp_code,
            expires_at=timezone.now() + timezone.timedelta(minutes=5)
        )
        
        # Send via Celery
        if not settings.DEBUG:
            send_sms_task.delay(phone_number, f"Your QuickDash login code is {otp_code}")
            
        return otp_code

    @staticmethod
    def verify_otp(phone_number, code):
        try:
            otp = OTP.objects.get(
                phone_number=phone_number,
                code=code,
                is_verified=False
            )
            
            if otp.is_expired():
                raise ValueError("OTP expired")
                
            otp.is_verified = True
            otp.save()
            
            user, created = User.objects.get_or_create(phone=phone_number)
            if created:
                user.role = 'CUSTOMER'
                user.save()
                
            return user, created
            
        except OTP.DoesNotExist:
            raise ValueError("Invalid OTP")