# apps/accounts/utils.py
import secrets
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
# [CHANGE] Django ka standard ValidationError hata kar DRF wala use karein
from rest_framework.exceptions import ValidationError 
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.core.cache import cache
from .models import PhoneOTP, UserSession
from .tasks import send_sms_task
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "")
    if not phone.startswith('+') and len(phone) == 10:
        phone = '+91' + phone
    return phone

def create_and_send_otp(phone: str, login_type: str):
    phone = normalize_phone(phone)
    # Crypto-secure 6 digit OTP
    otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    
    otp = PhoneOTP.create_otp(phone=phone, login_type=login_type, code=otp_code)
    
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
        # Ab ye 400 Bad Request return karega JSON format mein
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

def create_tokens_with_session(user, role, client, extra_claims=None, request=None, single_session_for_client=False):
    extra_claims = extra_claims or {}
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["client"] = client
    for k, v in extra_claims.items():
        refresh[k] = v

    jti = str(refresh["jti"])
    
    with transaction.atomic():
        if single_session_for_client:
            UserSession.objects.filter(
                user=user, client=client, is_active=True
            ).update(is_active=False, revoked_at=timezone.now())

        UserSession.objects.create(
            user=user, role=role, client=client, jti=jti,
            ip_address=get_client_ip(request)
        )

    access = refresh.access_token
    access["role"] = role
    for k, v in extra_claims.items():
        access[k] = v

    return {
        "access": str(access),
        "refresh": str(refresh),
        "refresh_jti": jti,
    }

@transaction.atomic
def rotate_refresh_token(old_refresh_token_str: str, request=None):
    old_token = RefreshToken(old_refresh_token_str)
    old_jti = str(old_token["jti"])
    
    old_token.blacklist()

    try:
        session = UserSession.objects.select_for_update().get(jti=old_jti, is_active=True)
    except UserSession.DoesNotExist:
        raise TokenError("Session not found or already revoked.")
    
    user = session.user
    
    refresh = RefreshToken.for_user(user)
    new_claims = {k: old_token.get(k) for k in ['user_id', 'role', 'client'] if k in old_token}
    new_claims["role"] = session.role
    new_claims["client"] = session.client
    for k, v in new_claims.items():
        refresh[k] = v
        
    new_jti = str(refresh["jti"])

    session.revoke()
    
    new_session = UserSession.objects.create(
        user=user, 
        role=session.role, 
        client=session.client, 
        jti=new_jti,
        device_id=session.device_id,
        ip_address=get_client_ip(request),
    )
    
    access = refresh.access_token
    access["role"] = new_session.role

    return {
        "access": str(access),
        "refresh": str(refresh),
        "refresh_jti": new_jti,
    }




def validate_staff_email_domain(email):
    """
    Staff login via Google is restricted to specific domains.
    """
    ALLOWED_DOMAINS = ['quickdash.com', 'quickdash.in']
    domain = email.split('@')[-1]
    if domain not in ALLOWED_DOMAINS:
        raise ValidationError(f"Email domain {domain} is not authorized for staff access.")
    return True