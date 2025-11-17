# apps/accounts/utils.py

import random
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .tasks import send_sms_task
from .models import PhoneOTP, UserSession, User

logger = logging.getLogger(__name__)
OTP_LENGTH = 6


def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "")
    if not phone.startswith('+'):
         # Assuming Indian numbers agar + nahi laga hai
         if len(phone) == 10:
             phone = '+91' + phone
    return phone


def generate_otp_code(length: int = OTP_LENGTH) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_otp_sms(phone: str, otp_code: str, login_type: str):
    """
    Yahaan aapka real SMS provider (jaise Twilio) integrate hoga.
    Abhi ke liye log print kar rahe:
    """
    # TODO: Production mein, isko Celery task se call karein
    logger.info(f"[SMS STUB] Sending OTP {otp_code} to {phone} for {login_type}")
    send_sms_task.delay(phone=phone, otp_code=otp_code, login_type=login_type)


def check_otp_rate_limit(phone: str, login_type: str, ip: str | None = None):
    """
    Simple enterprise-style rate limit:
    - same phone + login_type ke liye 60 seconds ke andar dusra OTP nahi
    - per day max 10 OTP per phone+login_type
    
    TODO: Production mein isko Redis-based counter se replace karein.
    """
    now = timezone.now()
    one_min_ago = now - timedelta(seconds=60)
    one_day_ago = now - timedelta(days=1)

    # 1 min limit
    recent = PhoneOTP.objects.filter(
        phone=phone,
        login_type=login_type,
        created_at__gte=one_min_ago,
    ).exists()
    if recent:
        raise ValidationError("OTP already sent recently. Please wait 60 seconds.")

    # daily limit
    daily_count = PhoneOTP.objects.filter(
        phone=phone,
        login_type=login_type,
        created_at__gte=one_day_ago,
    ).count()
    if daily_count >= 10:
        raise ValidationError("Too many OTP requests for today. Try again tomorrow.")


def create_and_send_otp(phone: str, login_type: str) -> PhoneOTP:
    phone = normalize_phone(phone)
    otp_code = generate_otp_code()
    
    # create_otp ab purane OTPs ko automatically invalid kar dega
    otp = PhoneOTP.create_otp(phone=phone, login_type=login_type, code=otp_code) 
    
    send_otp_sms(phone, otp_code, login_type)
    return otp


def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def invalidate_other_sessions_for_client(user, client, keep_jti=None):
    """
    Rider/Employee ke liye "Single Device Policy" laagu karta hai.
    """
    qs = UserSession.objects.filter(user=user, client=client, is_active=True)
    if keep_jti:
        qs = qs.exclude(jti=keep_jti)
    
    count = qs.count()
    if count > 0:
        logger.info(f"Revoking {count} old sessions for user {user.phone} on client {client}")
        qs.update(is_active=False, revoked_at=timezone.now())


def create_tokens_with_session(
    *,
    user,
    role: str,
    client: str,
    extra_claims: dict | None = None,
    device_info: dict | None = None,
    request=None,
    single_session_for_client: bool = False,
):
    """
    Enterprise style:
    - JWT (Refresh + Access) generate
    - extra claims inject
    - refresh["jti"] se UserSession create
    - Agar single_session_for_client=True, to purane sessions revoke kar deta hai.
    """
    extra_claims = extra_claims or {}
    device_info = device_info or {}

    refresh = RefreshToken.for_user(user)
    
    # Claims add karein
    refresh["role"] = role
    refresh["client"] = client
    for k, v in extra_claims.items():
        refresh[k] = v

    jti = str(refresh["jti"])
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    
    device_id = device_info.get("device_id", "")
    device_model = device_info.get("device_model", "")
    os_version = device_info.get("os_version", "")

    with transaction.atomic():
        # SINGLE SESSION POLICY
        if single_session_for_client:
            invalidate_other_sessions_for_client(user, client)
        
        # Purane sessions ko clean karein (Optional, agar multiple sessions allowed hain)
        if not single_session_for_client:
            MAX_ACTIVE_SESSIONS_PER_CLIENT = 5
            active_sessions = UserSession.objects.filter(
                user=user, client=client, is_active=True
            ).order_by("-created_at")
            if active_sessions.count() >= MAX_ACTIVE_SESSIONS_PER_CLIENT:
                for sess in active_sessions[MAX_ACTIVE_SESSIONS_PER_CLIENT - 1 :]:
                    sess.revoke()

        # Naya session record banayein
        UserSession.objects.create(
            user=user,
            role=role,
            client=client,
            jti=jti,
            user_agent=ua,
            ip_address=ip,
            device_id=device_id,
            device_model=device_model,
            os_version=os_version,
        )

    access = refresh.access_token
    # Access token mein bhi claims add karein
    access["role"] = role
    access["client"] = client
    for k, v in extra_claims.items():
        access[k] = v

    return {
        "access": str(access),
        "refresh": str(refresh),
        "access_expires_in": settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds(),
        "refresh_jti": jti,
    }


def rotate_refresh_token(old_refresh_token_str: str, request=None):
    """
    Refresh token ko rotate karein aur UserSession mein naya JTI update karein.
    """
    try:
        old_refresh = RefreshToken(old_refresh_token_str)
    except TokenError as e:
        logger.warning(f"Token rotation failed: {e}")
        raise

    user_id = old_refresh["user_id"]
    jti_old = str(old_refresh["jti"])

    try:
        user = User.objects.get(id=user_id)
        session = UserSession.objects.select_for_update().get(jti=jti_old, is_active=True)
    except (User.DoesNotExist, UserSession.DoesNotExist):
        raise TokenError("Session not found or already revoked.")

    # Naya refresh token banayein
    new_refresh = RefreshToken.for_user(user)
    
    # Purane claims copy karein
    claims_to_copy = ["role", "client", "customer_id", "rider_id", "rider_code", "employee_id", "employee_code", "warehouse_code", "employee_role", "admin_id"]
    for claim in claims_to_copy:
        if claim in old_refresh:
            new_refresh[claim] = old_refresh[claim]

    new_jti = str(new_refresh["jti"])
    
    # Session mein naya JTI update karein
    session.jti = new_jti
    session.save(update_fields=["jti"])

    access = new_refresh.access_token
    # Access token mein bhi claims copy karein
    for claim in claims_to_copy:
        if claim in new_refresh:
            access[claim] = new_refresh[claim]
            
    logger.info(f"Token rotated successfully for user {user.phone}")

    return {
        "access": str(access),
        "refresh": str(new_refresh),
        "refresh_jti": new_jti,
    }