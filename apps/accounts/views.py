from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import logging

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
        try:
            check_otp_rate_limit(phone, login_type, ip=get_client_ip(request))
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        # 1) OTP record dhoondo
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

        # 2) OTP verify
        is_valid, message = otp_record.is_valid(otp_input)
        if not is_valid:
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        # ===========================
        # 3) USER FETCH / CREATE
        # ===========================
        user = None
        created = False

        # ---- CUSTOMER LOGIN ----
        if login_type == "CUSTOMER":
            user, created = User.objects.get_or_create(phone=phone)

            if not hasattr(user, "customer_profile"):
                user_signed_up.send(sender=self.__class__, user=user, login_type="CUSTOMER")

            # [FIX] Only set is_customer if login_type is CUSTOMER
            if not user.is_customer:
                user.is_customer = True
                user.save(update_fields=["is_customer"])

        # ---- RIDER LOGIN ----
        elif login_type == "RIDER":
            try:
                user = User.objects.get(
                    phone=phone,
                    rider_profile__approval_status=RiderProfile.ApprovalStatus.APPROVED,
                )
            except User.DoesNotExist:
                return Response({"detail": "Rider not approved."}, status=status.HTTP_403_FORBIDDEN)

            if not user.is_rider:
                user.is_rider = True
                user.save(update_fields=["is_rider"])


        # ---- EMPLOYEE LOGIN ----
        elif login_type == "EMPLOYEE":
            try:
                user = User.objects.get(
                    phone=phone,
                    employee_profile__is_active_employee=True,
                )
            except User.DoesNotExist:
                return Response({"detail": "Employee not active."}, status=status.HTTP_403_FORBIDDEN)

            if not user.is_employee:
                user.is_employee = True
                user.save(update_fields=["is_employee"])

        if user is None:
            return Response(
                {"detail": "User not found after OTP verification."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ===========================
        # 4) JWT + SESSION CREATION
        # ===========================
        refresh = RefreshToken.for_user(user)
        refresh["role"] = login_type

        # store session for logout & tracking
        UserSession.objects.create(
            user=user,
            role=login_type,
            client=request.META.get("HTTP_USER_AGENT", "Unknown"),
            jti=refresh["jti"],
            ip_address=get_client_ip(request),
        )

        access = refresh.access_token
        access["role"] = login_type

        # ===========================
        # 5) RESPONSE
        # ===========================
        return Response(
            {
                "access": str(access),
                "refresh": str(refresh),
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

        # Reuse generic logic
        request._full_data = data
        return VerifyOTPView().post(request)


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
    """
    Customer app ke liye /customer/me/:
    - user basic info
    - customer profile
    - addresses
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        customer = user.customer_profile
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
