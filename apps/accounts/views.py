import logging
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import Throttled, ValidationError
from django.conf import settings

from .models import PhoneOTP, UserSession, Address, CustomerProfile, RiderProfile, EmployeeProfile
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    UserProfileSerializer,
    CustomerMeSerializer,
    AddressSerializer,
    AddressListSerializer,
)
from .utils import (
    create_and_send_otp,
    check_otp_rate_limit,
    get_client_ip,
    normalize_phone,
    create_tokens_with_session
)
from .permissions import IsCustomer

logger = logging.getLogger(__name__)
User = get_user_model()


class RequestOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = RequestOTPSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        login_type = serializer.validated_data['login_type']
        client_ip = get_client_ip(request)

        # Rate Limit Check
        try:
            check_otp_rate_limit(phone, login_type, ip=client_ip)
        except ValidationError as e:
            logger.warning(f"OTP Rate Limit hit: {phone} IP: {client_ip}")
            raise Throttled(detail=str(e))
        except Exception:
            logger.exception("Redis connection error during OTP limit check")
            return Response(
                {"detail": "Temporary system error. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Create OTP
        create_and_send_otp(phone, login_type)
        if settings.DEBUG:
            logger.info(f"Dev Hint: OTP sent to {phone} (Check Console/DB)")

        return Response({"message": "OTP sent successfully. Please check your SMS."}, status=status.HTTP_200_OK)


class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def perform_verification(self, request, validated_data):
        phone = normalize_phone(validated_data['phone'])
        otp_input = validated_data['otp']
        login_type = validated_data['login_type'].upper()

        # 1. Check OTP Record
        otp_record = PhoneOTP.objects.filter(
            phone=phone,
            login_type=login_type,
            is_used=False,
        ).last()

        if not otp_record:
            return Response({"detail": "OTP request not found or expired."}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, message = otp_record.is_valid(otp_input)
        if not is_valid:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Mark OTP Used
        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        # 3. GET OR VALIDATE USER BASED ON ROLE
        user = None
        created = False

        # CUSTOMER: Auto-create a dedicated customer user row
        if login_type == 'CUSTOMER':
            user = User.objects.filter(phone=phone, is_customer=True).first()
            if not user:
                user = User.objects.create(phone=phone, is_customer=True, is_active=True)
                created = True
            CustomerProfile.objects.get_or_create(user=user)

        # RIDER: Must have pre-existing rider user (separate row)
        elif login_type == 'RIDER':
            user = User.objects.filter(phone=phone, is_rider=True).first()
            if not user:
                return Response({"detail": "Rider account not found. Please register or contact support."},
                                status=status.HTTP_404_NOT_FOUND)
            if not hasattr(user, 'rider_profile'):
                return Response({"detail": "Rider profile incomplete. Contact Admin."}, status=status.HTTP_403_FORBIDDEN)
            if user.rider_profile.status == RiderProfile.RiderStatus.SUSPENDED:
                return Response({"detail": "Your rider account is suspended."}, status=status.HTTP_403_FORBIDDEN)

        # EMPLOYEE: Must have pre-existing employee user
        elif login_type == 'EMPLOYEE':
            user = User.objects.filter(phone=phone, is_employee=True).first()
            if not user:
                return Response({"detail": "Employee account not found."}, status=status.HTTP_404_NOT_FOUND)
            if not hasattr(user, 'employee_profile') or not user.employee_profile.is_active_employee:
                return Response({"detail": "Employee account inactive."}, status=status.HTTP_403_FORBIDDEN)

        else:
            return Response({"detail": "Invalid login type."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Send signup signal when created
        if created:
            try:
                from apps.accounts.signals import user_signed_up
                user_signed_up.send(sender=User, request=request, user=user, login_type=login_type)
            except Exception:
                logger.exception("Failed to send user_signed_up signal")

        # 5. Generate tokens and session
        tokens = create_tokens_with_session(
            user=user,
            role=login_type,
            client=request.META.get("HTTP_USER_AGENT", "Unknown"),
            request=request,
            single_session_for_client=False,
        )

        return Response({**tokens, "user": UserProfileSerializer(user).data, "is_new_user": created},
                        status=status.HTTP_200_OK)

    def get(self, request):
        return Response({"detail": "Please use POST to verify OTP."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_verification(request, serializer.validated_data)


class CustomerRequestOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["login_type"] = "CUSTOMER"

        serializer = RequestOTPSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        login_type = "CUSTOMER"

        try:
            check_otp_rate_limit(phone, login_type, ip=get_client_ip(request))
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        create_and_send_otp(phone, login_type)

        if settings.DEBUG:
            logger.info(f"Dev Hint: OTP sent to {phone} for CUSTOMER")

        return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)


class CustomerVerifyOTPView(VerifyOTPView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["login_type"] = "CUSTOMER"

        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return self.perform_verification(request, serializer.validated_data)


# --- Profile / Address Views ---

class MeView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_serializer = UserProfileSerializer(request.user)
        return Response(profile_serializer.data)


class CustomerMeView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        customer, _ = CustomerProfile.objects.get_or_create(user=user)
        addresses = user.addresses.all().order_by('-is_default', 'id')
        data = CustomerMeSerializer({"user": user, "customer": customer, "addresses": addresses}).data
        return Response(data)


class CustomerAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return AddressListSerializer
        return AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-id')

    def perform_create(self, serializer):
        make_default = serializer.validated_data.get("is_default", False)
        if make_default:
            Address.objects.filter(user=self.request.user, is_default=True).update(is_default=False)
        serializer.save(user=self.request.user)


class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        make_default = serializer.validated_data.get("is_default", False)
        if make_default:
            Address.objects.filter(user=self.request.user, is_default=True).exclude(id=self.get_object().id).update(is_default=False)
        serializer.save(user=self.request.user)


class SetDefaultAddressView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):
        try:
            address = Address.objects.get(pk=pk, user=request.user)
        except Address.DoesNotExist:
            return Response({"detail": "Address not found."}, status=404)

        Address.objects.filter(user=request.user, is_default=True).exclude(pk=pk).update(is_default=False)
        address.is_default = True
        address.save(update_fields=["is_default"])
        return Response({"detail": "Default address updated."}, status=200)


class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            try:
                jti = token['jti']
                UserSession.objects.filter(jti=jti).update(is_active=False, revoked_at=timezone.now())
            except Exception:
                pass

            return Response({"detail": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return Response({"error": "Invalid token or logout failed"}, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# SERVICE AVAILABILITY CHECKER PAGE
# ============================================
from django.views.generic import TemplateView


class LocationServiceCheckView(TemplateView):
    template_name = 'location_service_check.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Service Availability Checker'
        return context
