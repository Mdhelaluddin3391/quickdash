# apps/accounts/views.py
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import logging
from rest_framework.exceptions import Throttled, ValidationError

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

        # Rate Limit Check
        try:
            check_otp_rate_limit(phone, login_type, ip=client_ip)
        except ValidationError as e:
            raise Throttled(detail=str(e))
        except Exception:
            logger.exception("OTP rate limit error")
            raise ValidationError("Could not process OTP request.")

        # Create OTP (Utility decide karega SMS bhejna hai ya nahi)
        otp_obj = create_and_send_otp(phone, login_type)
        
        # --- [SECURITY LOGIC] ---
        response_data = {
            "message": "OTP sent successfully.",
        }

        # Sirf Debug mode mein OTP response mein bhejo testing ke liye
        if settings.DEBUG:
            response_data["dev_hint"] = otp_obj.otp_code

        return Response(response_data, status=status.HTTP_200_OK)


# ==========================
# GENERIC OTP VERIFY
# ==========================

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def perform_verification(self, request, validated_data):
        """
        Shared logic for verifying OTP and logging in the user.
        Ye function banaya gaya hai taaki code reuse ho sake bina request hack kiye.
        """
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
                user.save()
            # Ensure profile exists
            CustomerProfile.objects.get_or_create(user=user)
            
        elif login_type == 'RIDER':
            # Rider login logic (usually requires pre-approval)
            pass 

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


# ==========================
# CUSTOMER SPECIFIC ENDPOINTS
# ==========================

class CustomerRequestOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Force login_type
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["login_type"] = "CUSTOMER"
        
        serializer = RequestOTPSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        phone = serializer.validated_data["phone"]
        login_type = "CUSTOMER"
        
        try:
            check_otp_rate_limit(phone, login_type, ip=get_client_ip(request))
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_obj = create_and_send_otp(phone, login_type)
        
        response_data = {
            "message": "OTP sent successfully.",
        }
        if settings.DEBUG:
            response_data["dev_hint"] = otp_obj.otp_code

        return Response(response_data, status=status.HTTP_200_OK)


class CustomerVerifyOTPView(VerifyOTPView):
    """
    Inherits from VerifyOTPView but forces login_type='CUSTOMER'.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Force login_type in data
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data["login_type"] = "CUSTOMER"
        
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        
        # Call the shared verification logic directly
        # Yeh line sahi hai, purani wali crash kar rahi thi
        return self.perform_verification(request, serializer.validated_data)


# ==========================
# ME / PROFILE VIEWS
# ==========================

class MeView(views.APIView):
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
            # Fallback if profile missing
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


# ==========================
# ADDRESS VIEWS
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

        address.is_default = True
        address.save()
        return Response(
            {"detail": "Default address updated."},
            status=status.HTTP_200_OK,
        )


# ==========================
# LOGOUT VIEW
# ==========================

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
            logger.exception("Logout failed")
            return Response(
                {"error": "Logout failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )