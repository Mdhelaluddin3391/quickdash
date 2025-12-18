import logging
import uuid
import secrets 
from rest_framework import status, views, permissions, generics
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import Throttled, ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.views.generic import TemplateView

from .models import PhoneOTP, UserSession, CustomerProfile, EmployeeProfile, RiderProfile, Address
from .tasks import send_sms_task 
from .serializers import (
    SendOTPSerializer, 
    VerifyOTPSerializer, 
    CustomTokenObtainPairSerializer, 
    GoogleLoginSerializer,
    UserProfileSerializer,
    CustomerMeSerializer,
    AddressSerializer,
    AddressListSerializer,
)
from .utils import validate_staff_email_domain, check_otp_rate_limit
from .permissions import IsCustomer

logger = logging.getLogger(__name__)
User = get_user_model()

# ==========================================
# 1. SEND OTP (UNIFIED)
# ==========================================

class SendOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone = serializer.validated_data['phone']
        role = serializer.validated_data['role']
        client_ip = self.get_client_ip(request)

        # 1. Rate Limiting (Redis)
        check_otp_rate_limit(phone, role, ip=client_ip)

        # 2. Existence Checks (Strictly by Role)
        if role == 'RIDER':
            user_exists = User.objects.filter(phone=phone, is_rider=True).exists()
            if not user_exists:
                return Response(
                    {"detail": "No rider account found with this phone number."},
                    status=status.HTTP_404_NOT_FOUND
                )
            user = User.objects.filter(phone=phone, is_rider=True).first()
            if not hasattr(user, 'rider_profile'):
                 return Response({"detail": "Rider profile incomplete."}, status=status.HTTP_403_FORBIDDEN)

        elif role == 'EMPLOYEE':
            user_exists = User.objects.filter(phone=phone, is_employee=True).exists()
            if not user_exists:
                return Response(
                    {"detail": "No employee account found with this phone number."},
                    status=status.HTTP_404_NOT_FOUND
                )
            user = User.objects.filter(phone=phone, is_employee=True).first()
            if not hasattr(user, 'employee_profile'):
                 return Response({"detail": "Employee profile incomplete."}, status=status.HTTP_403_FORBIDDEN)

        # 3. Generate Random OTP
        code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        
        otp_obj, error = PhoneOTP.create_otp(phone, role, code)
        if error:
            return Response({"detail": error}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # 4. Send SMS Logic
        if settings.DEBUG:
            logger.info(f"OTP for {phone} ({role}): {code}")
            return Response({"detail": "OTP sent (Dev Mode).", "dev_code": code})
        else:
            send_sms_task.delay(phone=phone, otp_code=code, login_type=role)
            return Response({"detail": "OTP sent successfully via SMS."})

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # FIX: Take the LAST IP (trusted proxy) to prevent spoofing
            # Previous [0] was vulnerable to client-side header injection
            return x_forwarded_for.split(',')[-1].strip()
        return request.META.get('REMOTE_ADDR')


# ==========================================
# 2. LOGIN WITH OTP (UNIFIED)
# ==========================================

class LoginWithOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        otp_code = serializer.validated_data['otp']
        role = serializer.validated_data['role']
        device_id = serializer.validated_data.get('device_id', '')
        
        # 1. Validate OTP
        otp_record = PhoneOTP.objects.filter(phone=phone, login_type=role).order_by('-created_at').first()
        
        if not otp_record:
            return Response({"detail": "OTP not found. Request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, message = otp_record.is_valid(otp_code)
        if not is_valid:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        
        # 2. Get or Create User
        user = None
        created = False

        if role == 'CUSTOMER':
            user = User.objects.filter(phone=phone, is_customer=True).first()
            if not user:
                user = User.objects.create_user(phone=phone, is_customer=True)
                CustomerProfile.objects.create(user=user)
                created = True
            user.app_role = 'CUSTOMER'
            user.save()

        elif role == 'RIDER':
            user = User.objects.filter(phone=phone, is_rider=True).first()
            if not user:
                return Response({"detail": "Rider account does not exist."}, status=status.HTTP_403_FORBIDDEN)
            if not hasattr(user, 'rider_profile'):
                 return Response({"detail": "Rider profile missing."}, status=status.HTTP_403_FORBIDDEN)
            if user.rider_profile.approval_status != RiderProfile.ApprovalStatus.APPROVED:
                return Response({"detail": "Rider account is not approved."}, status=status.HTTP_403_FORBIDDEN)
            user.app_role = 'RIDER'
            user.save()

        elif role == 'EMPLOYEE':
            user = User.objects.filter(phone=phone, is_employee=True).first()
            if not user:
                return Response({"detail": "Employee account does not exist."}, status=status.HTTP_403_FORBIDDEN)
            if not hasattr(user, 'employee_profile'):
                 return Response({"detail": "Employee profile missing."}, status=status.HTTP_403_FORBIDDEN)
            if not user.employee_profile.is_active_employee:
                return Response({"detail": "Employee account is inactive."}, status=status.HTTP_403_FORBIDDEN)
            user.app_role = 'EMPLOYEE'
            user.save()

        # 3. Mark OTP as used
        otp_record.is_used = True
        otp_record.save()

        # 4. Create Session
        jti = str(uuid.uuid4())
        UserSession.objects.create(
            user=user,
            role=role,
            jti=jti,
            client=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=self.get_client_ip(request),
            device_id=device_id
        )

        # 5. Generate Token
        user.current_session_jti = jti 
        refresh = CustomTokenObtainPairSerializer.get_token(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": role
            },
            "is_new_user": created
        })

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # FIX: Take the LAST IP (trusted proxy) to prevent spoofing
            # Previous [0] was vulnerable to client-side header injection
            return x_forwarded_for.split(',')[-1].strip()
        return request.META.get('REMOTE_ADDR')


# ==========================================
# 3. GOOGLE LOGIN (STAFF ONLY)
# ==========================================
class StaffGoogleLoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['id_token']

        try:
            id_info = id_token.verify_oauth2_token(
                token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            email = id_info['email']
            
            validate_staff_email_domain(email)

            user = User.objects.filter(email=email, is_employee=True).first()

            if not user:
                return Response({"detail": "No staff account found with this email."}, status=status.HTTP_403_FORBIDDEN)

            if not hasattr(user, 'employee_profile'):
                 return Response({"detail": "User is not an employee."}, status=status.HTTP_403_FORBIDDEN)
            
            profile = user.employee_profile
            if not profile.can_access_admin_panel():
                return Response({"detail": "You do not have permission to access the admin panel."}, status=status.HTTP_403_FORBIDDEN)

            user.is_staff = True 
            user.app_role = 'ADMIN_PANEL'
            user.save()

            jti = str(uuid.uuid4())
            UserSession.objects.create(
                user=user,
                role='ADMIN_PANEL',
                jti=jti,
                client=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=request.META.get('REMOTE_ADDR')
            )

            user.current_session_jti = jti
            refresh = CustomTokenObtainPairSerializer.get_token(user)

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            })

        except ValueError as e:
            return Response({"detail": f"Invalid Token: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Google Login Error: {str(e)}")
            return Response({"detail": "Authentication failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 4. PROFILE & ADDRESS MANAGEMENT
# ==========================================

class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile_serializer = UserProfileSerializer(request.user)
        return Response(profile_serializer.data)


class CustomerMeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        customer, _ = CustomerProfile.objects.get_or_create(user=user)
        addresses = user.addresses.all().order_by('-is_default', 'id')
        data = CustomerMeSerializer({"user": user, "customer": customer, "addresses": addresses}).data
        return Response(data)


class CustomerAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

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
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        make_default = serializer.validated_data.get("is_default", False)
        if make_default:
            Address.objects.filter(user=self.request.user, is_default=True).exclude(id=self.get_object().id).update(is_default=False)
        serializer.save(user=self.request.user)


class SetDefaultAddressView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            # Revoke session
            try:
                jti = token['jti']
                UserSession.objects.filter(jti=jti).update(is_active=False, revoked_at=timezone.now())
            except Exception:
                pass

            return Response({"detail": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return Response({"error": "Invalid token or logout failed"}, status=status.HTTP_400_BAD_REQUEST)


class LocationServiceCheckView(TemplateView):
    template_name = 'location_service_check.html'