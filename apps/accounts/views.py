# apps/accounts/views.py
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import random

from .models import PhoneOTP, UserSession
from .serializers import (
    RequestOTPSerializer, 
    VerifyOTPSerializer, 
    UserProfileSerializer,
)

User = get_user_model()

class RequestOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = RequestOTPSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone = serializer.validated_data['phone']
        login_type = serializer.validated_data['login_type']
        
        otp_code = str(random.randint(100000, 999999))
        PhoneOTP.create_otp(phone, login_type, otp_code)
        
        return Response({
            "message": "OTP sent successfully.", 
            "dev_hint": otp_code if settings.DEBUG else None
        }, status=status.HTTP_200_OK)

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
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
            if login_type == 'RIDER':
                user.is_rider = True
            elif login_type == 'EMPLOYEE':
                user.is_employee = True
            else:
                user.is_customer = True
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

class MeView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_serializer = UserProfileSerializer(request.user)
        return Response(profile_serializer.data)

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
