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
from django.core.cache import cache
from rest_framework.exceptions import Throttled
import logging

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

def check_otp_rate_limit(identifier, action_type, limit=3, period=300, ip=None):
    """
    Rate limits OTP actions by Phone OR IP.
    
    :param identifier: Phone number or User ID
    :param action_type: 'LOGIN_ATTEMPT', 'SEND_OTP', etc.
    :param limit: Max attempts allowed
    :param period: Time window in seconds
    :param ip: Client IP address (optional but recommended for security)
    """
    
    # 1. Throttle by Identifier (Phone)
    key_id = f"throttle_{action_type}_{identifier}"
    attempts_id = cache.get(key_id, 0)
    
    if attempts_id >= limit:
        logger.warning(f"Throttling {identifier} for {action_type}")
        raise Throttled(detail=f"Too many attempts. Try again in {period//60} minutes.")
        
    # 2. Throttle by IP (Prevent Distributed Attacks)
    if ip:
        key_ip = f"throttle_{action_type}_ip_{ip}"
        attempts_ip = cache.get(key_ip, 0)
        # Allow more leeway for IP (e.g., 3x limit) in case of NAT
        if attempts_ip >= (limit * 5): 
            logger.warning(f"Blocking IP {ip} for {action_type}")
            raise Throttled(detail="Too many requests from this network.")

    # Increment Counters
    # We use 'set' with nx=True or similar, but for simple cache:
    if attempts_id == 0:
        cache.set(key_id, 1, timeout=period)
    else:
        try:
            cache.incr(key_id)
        except ValueError:
            cache.set(key_id, 1, timeout=period)

    if ip:
        if attempts_ip == 0:
            cache.set(key_ip, 1, timeout=period)
        else:
            try:
                cache.incr(key_ip)
            except ValueError:
                 cache.set(key_ip, 1, timeout=period)

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