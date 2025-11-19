from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserProfileSerializer,
    ChangePasswordSerializer,
    RiderProfileSerializer
)
from .models import PhoneOTP, RiderProfile, StoreStaffProfile, UserSession, EmployeeProfile
from .permissions import IsCustomer, IsRider, IsEmployee

# Use get_user_model() to get the custom User model
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
        
        # Verify OTP (Development bypass: 123456)
        if otp != "123456":
            otp_record = PhoneOTP.objects.filter(phone=phone).first()
            if not otp_record or not otp_record.is_valid(otp):
                return Response({"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST)
            # Mark OTP as used
            otp_record.is_used = True
            otp_record.save()
        
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({"error": "User not found. Please register first."}, status=status.HTTP_404_NOT_FOUND)
            
        # Generate Tokens
        refresh = RefreshToken.for_user(user)
        
        # Create UserSession (Optional but good for tracking)
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
    """
    API view to retrieve and update the logged-in user's profile.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    """
    API view to change the user's password.
    """
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
    """
    API view to logout the user by blacklisting the refresh token.
    """
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
    """
    API view for customers to get their profile details.
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

class RiderMeView(views.APIView):
    """
    API view for riders to get and update their profile.
    """
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
    """
    API view for employees to get their profile details.
    """
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