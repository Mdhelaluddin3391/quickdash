import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from .models import PhoneOTP, UserSession, User

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "")
    if not phone.startswith('+') and len(phone) == 10:
        phone = '+91' + phone
    return phone

def create_and_send_otp(phone: str, login_type: str):
    phone = normalize_phone(phone)
    otp_code = "".join(str(random.randint(0, 9)) for _ in range(6))
    otp = PhoneOTP.create_otp(phone=phone, login_type=login_type, code=otp_code)
    # Production mein yahan SMS service call hogi. Abhi ke liye print kar rahe hain.
    print(f"--- OTP for {phone}: {otp_code} ---")
    return otp

def check_otp_rate_limit(phone: str, login_type: str, ip=None):
    # Simple rate limiting logic
    pass 

def get_client_ip(request):
    if not request: return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

def create_tokens_with_session(user, role, client, extra_claims=None, device_info=None, request=None, single_session_for_client=False):
    extra_claims = extra_claims or {}
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["client"] = client
    for k, v in extra_claims.items():
        refresh[k] = v

    jti = str(refresh["jti"])
    
    if single_session_for_client:
        UserSession.objects.filter(user=user, client=client, is_active=True).update(is_active=False, revoked_at=timezone.now())

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