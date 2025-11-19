# apps/accounts/utils.py
import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
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
    
    # Asynchronous SMS task ko call karein (optional for non-prod)
    # from .tasks import send_sms_task
    # send_sms_task.delay(phone=phone, otp_code=otp_code, login_type=login_type)
    
    return otp

def get_client_ip(request):
    if not request: return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

def check_otp_rate_limit(phone: str, login_type: str, ip=None):
    """
    Temporary simple rate limiting logic: Check if user already has a pending OTP.
    TODO: Production mein Redis based rate limiter use karein (e.g., django-ratelimit).
    """
    last_otp = PhoneOTP.objects.filter(
        phone=phone, 
        login_type=login_type
    ).order_by('-created_at').first()
    
    # Last OTP 60 seconds se pehle nahi aana chahiye
    if last_otp and last_otp.created_at > timezone.now() - timedelta(seconds=60):
        raise ValidationError("OTP request limit reached. Please wait one minute.")


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
            # Purani sessions ko revoke karein (e.g., Rider/Employee single device policy)
            UserSession.objects.filter(
                user=user, client=client, is_active=True
            ).update(is_active=False, revoked_at=timezone.now())

        # Naya session banayein
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