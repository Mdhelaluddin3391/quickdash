import secrets
import logging
import uuid
from django.conf import settings
from django.utils import timezone
from django.db import transaction
# USE ONLY DRF ValidationError for API responses
from rest_framework.exceptions import ValidationError 
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.core.cache import cache
from .models import PhoneOTP, UserSession
from .tasks import send_sms_task

logger = logging.getLogger(__name__)

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "")
    if not phone.startswith('+') and len(phone) == 10:
        phone = '+91' + phone
    return phone

def create_and_send_otp(phone: str, login_type: str):
    """
    Creates OTP and triggers SMS task.
    """
    phone = normalize_phone(phone)
    # Crypto-secure 6 digit OTP
    # In prod use secrets.randbelow(1000000) and zfill
    otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    
    otp, error = PhoneOTP.create_otp(phone=phone, login_type=login_type, code=otp_code)
    
    if error:
         # Propagate limit errors
         raise ValidationError({"detail": error})

    if settings.DEBUG:
        logger.info(f"[TEST OTP] {phone}: {otp_code}")
    else:
        send_sms_task.delay(phone=phone, otp_code=otp_code, login_type=login_type)
    
    return otp




def get_client_ip(request):
    if not request: return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

def check_otp_rate_limit(phone: str, login_type: str, ip=None):
    """
    Prevents OTP spam using Redis atomic operations.
    """
    # 1. Phone Throttle (1 request per 60s)
    rate_limit_key = f"otp_limit:{login_type}:{phone}"
    
    is_allowed = cache.set(rate_limit_key, "locked", timeout=60, nx=True)
    
    if not is_allowed:
        ttl = cache.ttl(rate_limit_key)
        raise ValidationError({"detail": f"Please wait {ttl} seconds before requesting another OTP."})

    # 2. IP Throttle (Max 20 requests per hour)
    if ip:
        ip_key = f"otp_spam_ip:{ip}"
        try:
            request_count = cache.incr(ip_key)
        except ValueError:
            cache.set(ip_key, 1, timeout=3600)
            request_count = 1
            
        if request_count > 20: 
             logger.warning(f"OTP Spam detected from IP: {ip}")
             raise ValidationError({"detail": "Too many requests from this IP. Try again later."})

def validate_staff_email_domain(email):
    """
    Staff login via Google is restricted to specific domains.
    """
    ALLOWED_DOMAINS = ['quickdash.com', 'quickdash.in']
    domain = email.split('@')[-1]
    if domain not in ALLOWED_DOMAINS:
        raise ValidationError(f"Email domain {domain} is not authorized for staff access.")
    return True


def create_tokens_with_session(user, role, client, request):
    """
    Creates a user session and generates JWT tokens.
    """
    # Import inside function to avoid circular dependency with serializers.py
    from .serializers import CustomTokenObtainPairSerializer

    jti = str(uuid.uuid4())
    ip_address = get_client_ip(request)
    
    UserSession.objects.create(
        user=user,
        role=role,
        jti=jti,
        client=client,
        ip_address=ip_address
    )

    # Link the JTI to the user for the token claim
    user.current_session_jti = jti
    refresh = CustomTokenObtainPairSerializer.get_token(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }