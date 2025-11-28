# apps/accounts/utils.py
import random
import secrets
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
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
    Creates OTP and decides how to send it based on Environment.
    """
    phone = normalize_phone(phone)
    # 6-digit random code
    otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    
    # Save to DB
    otp = PhoneOTP.create_otp(phone=phone, login_type=login_type, code=otp_code)
    
    # --- [SECURITY LOGIC] ---
    if settings.DEBUG:
        print(f"\n [TESTING] OTP for {phone}: {otp_code} \n")
        logger.info(f"Test OTP generated for {phone}: {otp_code}")
    else:
        send_sms_task.delay(phone=phone, otp_code=otp_code, login_type=login_type)
    
    return otp

def get_client_ip(request):
    if not request: return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

def check_otp_rate_limit(phone: str, login_type: str, ip=None):
    rate_limit_key = f"otp_limit:{login_type}:{phone}"
    if cache.get(rate_limit_key):
        ttl = cache.ttl(rate_limit_key) if hasattr(cache, 'ttl') else 60
        raise ValidationError(f"Please wait {ttl} seconds before requesting another OTP.")

    cache.set(rate_limit_key, "locked", timeout=60)
    
    if ip:
        ip_key = f"otp_spam_ip:{ip}"
        request_count = cache.get(ip_key, 0)
        if request_count > 20: 
             raise ValidationError("Too many requests from this IP. Try again later.")
        cache.set(ip_key, request_count + 1, timeout=3600)

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
    """
    JWT Rotation Logic: Purane refresh token ko blacklist karta hai aur naya deta hai.
    """
    # 1. Purana Token Validate aur Blacklist karein
    old_token = RefreshToken(old_refresh_token_str)
    old_jti = str(old_token["jti"])
    
    # Blacklist the old token
    old_token.blacklist()

    # 2. Purana Session dhoondein aur uske User ko fetch karein
    try:
        session = UserSession.objects.select_for_update().get(jti=old_jti, is_active=True)
    except UserSession.DoesNotExist:
        raise TokenError("Session not found or already revoked.")
    
    user = session.user
    
    # 3. Naya Token Set banayein
    refresh = RefreshToken.for_user(user)
    
    # Purane claims copy karein (role, client, aur custom claims)
    new_claims = {k: old_token.get(k) for k in ['user_id', 'role', 'client'] if k in old_token}
    
    # Add custom claims
    new_claims["role"] = session.role
    new_claims["client"] = session.client
    for k, v in new_claims.items():
        refresh[k] = v
        
    new_jti = str(refresh["jti"])

    # 4. Session Update karein (Old session ko revoke karke naye jti ke saath update karein)
    session.revoke()
    
    # Naya Session Record Create Karein
    new_session = UserSession.objects.create(
        user=user, 
        role=session.role, 
        client=session.client, 
        jti=new_jti,
        device_id=session.device_id,
        ip_address=get_client_ip(request),
    )
    
    # 5. Tokens return karein
    access = refresh.access_token
    access["role"] = new_session.role

    return {
        "access": str(access),
        "refresh": str(refresh),
        "refresh_jti": new_jti,
    }