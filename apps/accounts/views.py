from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import logging
from rest_framework.exceptions import Throttled, ValidationError
from .utils import create_tokens_with_session

from .models import PhoneOTP, UserSession, RiderProfile, Address, CustomerProfile
from .signals import user_signed_up
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    UserProfileSerializer,
    CustomerMeSerializer,
    AddressSerializer,
)
from .utils import (
    create_and_send_otp,
    check_otp_rate_limit,
    get_client_ip,
    normalize_phone,
)
from .permissions import IsCustomer  # existing permission :contentReference[oaicite:7]{index=7}
from .utils import normalize_phone, get_client_ip  # already in utils.py :contentReference[oaicite:2]{index=2}

logger = logging.getLogger(__name__)
User = get_user_model()


# ==========================
# GENERIC OTP REQUEST
# ==========================

class RequestOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = RequestOTPSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        login_type = serializer.validated_data['login_type']
        client_ip = get_client_ip(request)

        try:
            check_otp_rate_limit(phone, login_type, ip=client_ip)
        except ValidationError as e:
            logger.warning(
                "OTP rate limit exceeded",
                extra={"phone": phone, "login_type": login_type, "ip": client_ip},
            )
            # DRF Throttled → maps nicely to 429
            raise Throttled(detail=str(e))
        except Exception as e:
            logger.exception(
                "Unexpected error in OTP rate limiting",
                extra={"phone": phone, "login_type": login_type, "ip": client_ip},
            )
            raise ValidationError("Could not process OTP request. Please try again.")

        otp_obj = create_and_send_otp(phone, login_type)
        logger.info(
            "OTP requested",
            extra={"phone": phone, "login_type": login_type, "ip": client_ip},
        )

        return Response(
            {
                "message": "OTP sent successfully.",
                "dev_hint": otp_obj.otp_code if settings.DEBUG else None,
            },
            status=status.HTTP_200_OK,
        )


# ==========================
# GENERIC OTP VERIFY (3 roles)
# ==========================

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = normalize_phone(serializer.validated_data['phone'])
        otp_input = serializer.validated_data['otp']
        login_type = serializer.validated_data['login_type']
        client_ip = get_client_ip(request)

        try:
            check_otp_rate_limit(phone, login_type, ip=client_ip)
        except ValidationError as e:
            raise Throttled(detail=str(e))

        otp_record = PhoneOTP.objects.filter(
            phone=phone,
            login_type=login_type,
            is_used=False,
        ).last()

        if not otp_record:
            return Response(
                {"detail": "OTP request not found or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_valid, message = otp_record.is_valid(otp_input)
        if not is_valid:
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        # ... existing user creation logic ...

        tokens = create_tokens_with_session(
            user=user,
            role=login_type,
            client=request.META.get("HTTP_USER_AGENT", "Unknown"),
            request=request,
            single_session_for_client=False,
        )

        return Response(
            {
                **tokens,
                "user": UserProfileSerializer(user).data,
                "is_new_user": created,
            },
            status=status.HTTP_200_OK,
        )



# ==========================
# SHORTCUT: CUSTOMER-SPECIFIC OTP ENDPOINTS
# (TAKI FRONTEND KO login_type bhejna na pade)
# ==========================

class CustomerRequestOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = {
            "phone": request.data.get("phone"),
            "login_type": "CUSTOMER",
        }
        request._full_data = data  # DRF hack na karein, sidha serializer me
        serializer = RequestOTPSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        login_type = "CUSTOMER"

        phone = normalize_phone(phone)
        try:
            check_otp_rate_limit(phone, login_type, ip=get_client_ip(request))
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp_obj = create_and_send_otp(phone, login_type)
        return Response(
            {
                "message": "OTP sent successfully.",
                "dev_hint": otp_obj.otp_code if settings.DEBUG else None,
            },
            status=status.HTTP_200_OK,
        )


class CustomerVerifyOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = {
            "phone": request.data.get("phone"),
            "otp": request.data.get("otp"),
            "login_type": "CUSTOMER",
        }
        serializer = VerifyOTPSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        # directly call logic used in VerifyOTPView via a helper
        return VerifyOTPView().post(request._request.__class__(**{**request.__dict__, "data": data}))


# ==========================
# ME VIEWS
# ==========================

class MeView(views.APIView):
    """
    Generic /me/ — bas User basic details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_serializer = UserProfileSerializer(request.user)
        return Response(profile_serializer.data)


class CustomerMeView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        try:
            customer = user.customer_profile
        except ObjectDoesNotExist:
            return Response(
                {"detail": "Customer profile not found for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        addresses = user.addresses.all().order_by('-is_default', 'id')
        data = CustomerMeSerializer(
            {
                "user": user,
                "customer": customer,
                "addresses": addresses,
            }
        ).data
        return Response(data)

# ==========================
# CUSTOMER ADDRESSES CRUD
# ==========================

class CustomerAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', 'id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class SetDefaultAddressView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):
        try:
            address = Address.objects.get(pk=pk, user=request.user)
        except Address.DoesNotExist:
            return Response(
                {"detail": "Address not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # is_default handling model.save me already hai
        address.is_default = True
        address.save()
        return Response(
            {"detail": "Default address updated."},
            status=status.HTTP_200_OK,
        )


# ==========================
# LOGOUT VIEW (existing)
# ==========================

class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            try:
                jti = token['jti']
                UserSession.objects.filter(jti=jti).update(
                    is_active=False,
                    revoked_at=timezone.now(),
                )
            except Exception:
                logger.exception("Failed to revoke UserSession via JTI")

            return Response(
                {"detail": "Logged out successfully"},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except Exception as e:
            logger.exception(
                "Logout failed for user %s: %s",
                getattr(request, 'user', 'unknown'),
                e,
            )
            return Response(
                {"error": "Logout failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
