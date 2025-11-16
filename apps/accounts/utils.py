import random
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PhoneOTP, UserSession


def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "")
    # TODO: yaha +91 attach logic dal sakte ho
    return phone


def generate_otp_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_otp_sms(phone: str, otp_code: str, login_type: str):
    """
    REAL enterprise me yaha SMS provider integrate hoga.
    Abhi ke liye log print kar rahe:
    """
    print(f"[SMS STUB] Sending OTP {otp_code} to {phone} for {login_type}")


def create_and_send_otp(phone: str, login_type: str) -> PhoneOTP:
    phone = normalize_phone(phone)
    otp_code = generate_otp_code()
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


def create_tokens_with_session(*, user, role: str, client: str,
                               extra_claims: dict | None = None,
                               request=None):
    """
    Enterprise style:
    - JWT (Refresh + Access) generate
    - extra claims inject
    - refresh["jti"] se UserSession create
    """
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["client"] = client

    if extra_claims:
        for k, v in extra_claims.items():
            refresh[k] = v

    jti = str(refresh["jti"])
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""

    UserSession.objects.create(
        user=user,
        role=role,
        client=client,
        jti=jti,
        user_agent=ua,
        ip_address=ip,
    )

    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
    }
