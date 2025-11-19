# apps/accounts/views.py
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings # <-- Added for DEBUG check
import random

from .models import PhoneOTP, RiderProfile, EmployeeProfile, UserSession
from .serializers import (
    RequestOTPSerializer, 
    VerifyOTPSerializer, 
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserProfileSerializer,
    ChangePasswordSerializer,
    RiderProfileSerializer
)
from .permissions import IsCustomer, IsRider, IsEmployee

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """
    API view for registering a new user.
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

class UserLoginView(views.APIView):
    """
    API view for user login using phone number and OTP.
    """
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']
        
        # --- SECURITY FIX START ---
        # Verify OTP (Development bypass: 123456 only if DEBUG is True)
        bypass_otp = getattr(settings, 'DEBUG', False) and otp == "123456"
        
        if not bypass_otp:
            otp_record = PhoneOTP.objects.filter(phone=phone).first()
            if not otp_record or not otp_record.is_valid(otp):
                return Response({"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST)
            # Mark OTP as used
            otp_record.is_used = True
            otp_record.save()
        # --- SECURITY FIX END ---
        
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({"error": "User not found. Please register first."}, status=status.HTTP_404_NOT_FOUND)
            
        # Generate Tokens
        refresh = RefreshToken.for_user(user)
        
        # Create UserSession
        UserSession.objects.create(
            user=user,
            role=user.app_role,
            client="mobile_app",
            jti=refresh['jti'],
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserProfileSerializer(user).data
        })

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            if not user.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(serializer.data.get("new_password"))
            user.save()
            return Response({"status": "success", "code": status.HTTP_200_OK, "message": "Password updated successfully"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Invalidate session
            UserSession.objects.filter(jti=token['jti']).update(is_active=False, revoked_at=timezone.now())
            
            return Response({"detail": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# --- Role Based Views ---

class CustomerMeView(views.APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

class RiderMeView(views.APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        try:
            profile = RiderProfile.objects.get(user=request.user)
            return Response(RiderProfileSerializer(profile).data)
        except RiderProfile.DoesNotExist:
             return Response({"error": "Rider profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        try:
            profile = RiderProfile.objects.get(user=request.user)
        except RiderProfile.DoesNotExist:
             return Response({"error": "Rider profile not found."}, status=status.HTTP_404_NOT_FOUND)
             
        serializer = RiderProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EmployeeMeView(views.APIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        try:
            profile = EmployeeProfile.objects.get(user=request.user)
            return Response({
                "employee_code": profile.employee_code,
                "role": profile.role,
                "warehouse_code": profile.warehouse_code,
                "user": UserProfileSerializer(request.user).data
            })
        except EmployeeProfile.DoesNotExist:
            return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)


class RequestOTPView(views.APIView):
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            login_type = serializer.validated_data['login_type']
            
            otp_code = str(random.randint(100000, 999999))
            PhoneOTP.create_otp(phone, login_type, otp_code)
            
            return Response({
                "message": "OTP sent successfully.", 
                "dev_hint": otp_code if settings.DEBUG else None
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(views.APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            otp_input = serializer.validated_data['otp']
            login_type = serializer.validated_data['login_type']

            otp_record = PhoneOTP.objects.filter(phone=phone, login_type=login_type, is_used=False).last()
            
            if not otp_record:
                return Response({"error": "OTP request not found or expired."}, status=status.HTTP_400_BAD_REQUEST)

            is_valid, message = otp_record.is_valid(otp_input)
            if not is_valid:
                return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

            user, created = User.objects.get_or_create(phone=phone)
            
            if created:
                user.app_role = login_type
                if login_type == 'RIDER': user.is_rider = True
                elif login_type == 'EMPLOYEE': user.is_employee = True
                else: user.is_customer = True
                user.save()
            
            refresh = RefreshToken.for_user(user)
            
            UserSession.objects.create(
                user=user,
                role=user.app_role,
                client=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                jti=refresh['jti'],
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserProfileSerializer(user).data,
                "is_new_user": created
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)