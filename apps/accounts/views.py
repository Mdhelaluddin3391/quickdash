# apps/accounts/views.py
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import Throttled, ValidationError
from django.conf import settings

from .models import PhoneOTP, UserSession, Address, CustomerProfile
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

        # 1. Rate Limit Check
        try:
            check_otp_rate_limit(phone, login_type, ip=client_ip)
        except ValidationError as e:
            logger.warning(f"OTP Rate Limit hit: {phone} IP: {client_ip}")
            raise Throttled(detail=str(e))
        except Exception as e:
            logger.exception("Redis connection error during OTP limit check")
            # Fail open or closed depending on policy. Here we fail closed for security.
            return Response(
                {"detail": "Temporary system error. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # 2. Create OTP
        # Note: create_and_send_otp handles the SMS logic internally
        create_and_send_otp(phone, login_type)
        
        # [SECURITY FIX]: Never send the OTP code in the response, even in DEBUG.
        # Developers should check console logs or DB.
        if settings.DEBUG:
            logger.info(f"Dev Hint: OTP sent to {phone}")

        return Response(
            {"message": "OTP sent successfully. Please check your SMS."},
            status=status.HTTP_200_OK
        )


class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def perform_verification(self, request, validated_data):
        phone = normalize_phone(validated_data['phone'])
        otp_input = validated_data['otp']
        login_type = validated_data['login_type']
        
        # 1. Check OTP Record
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
            # Security: Increment attempts handled inside model logic, but we enforce failure response here
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Mark OTP Used
        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        # 3. Get or Create User
        user, created = User.objects.get_or_create(phone=phone)

        # 4. Update Role Flags & Profiles
        if login_type == 'CUSTOMER':
            if not user.is_customer:
                user.is_customer = True
                user.save(update_fields=['is_customer'])
            # Ensure profile exists
            CustomerProfile.objects.get_or_create(user=user)
            
        elif login_type == 'RIDER':
            # Rider must be pre-approved or created via admin/onboarding flow usually.
            if not user.is_rider:
                return Response(
                    {"detail": "Rider account does not exist or is not active."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # 5. Generate Tokens
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

        return Response(
            {"message": "OTP sent successfully."},
            status=status.HTTP_200_OK
        )


class CustomerVerifyOTPView(VerifyOTPView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["login_type"] = "CUSTOMER"
        
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return self.perform_verification(request, serializer.validated_data)


# --- Standard Profile Views (Unchanged logic, just ensure imports match) ---

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
        data = CustomerMeSerializer(
            {
                "user": user,
                "customer": customer,
                "addresses": addresses,
            }
        ).data
        return Response(data)


class CustomerAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-id')

    def perform_create(self, serializer):
        make_default = serializer.validated_data.get("is_default", False)

        # If new address is default → purane ko false karo
        if make_default:
            Address.objects.filter(
                user=self.request.user,
                is_default=True
            ).update(is_default=False)

        serializer.save(user=self.request.user)



class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        make_default = serializer.validated_data.get("is_default", False)

        if make_default:
            # Current user ke purane default ko false karo
            Address.objects.filter(
                user=self.request.user,
                is_default=True
            ).exclude(id=self.get_object().id).update(is_default=False)

        serializer.save(user=self.request.user)



class SetDefaultAddressView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):
        try:
            address = Address.objects.get(pk=pk, user=request.user)
        except Address.DoesNotExist:
            return Response({"detail": "Address not found."}, status=404)

        # Purane default ko hatao
        Address.objects.filter(
            user=request.user,
            is_default=True
        ).exclude(pk=pk).update(is_default=False)

        # Naye ko default banao
        address.is_default = True
        address.save(update_fields=["is_default"])

        return Response({"detail": "Default address updated."}, status=200)


class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            # Revoke session if tracking exists
            try:
                jti = token['jti']
                UserSession.objects.filter(jti=jti).update(
                    is_active=False,
                    revoked_at=timezone.now(),
                )
            except Exception:
                pass

            return Response(
                {"detail": "Logged out successfully"},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return Response(
                {"error": "Invalid token or logout failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )