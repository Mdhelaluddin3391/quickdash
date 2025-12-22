import uuid
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.utils.throttle import BurstRateThrottle

from .services import AuthService
from .serializers import OTPRequestSerializer, OTPVerifySerializer, UserSerializer

class SendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [BurstRateThrottle]  # Strict IP-based throttling

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        AuthService.request_otp(
            phone=serializer.validated_data['phone'],
            role=serializer.validated_data['role']
        )
        
        return Response(
            {"message": "OTP sent successfully"}, 
            status=status.HTTP_200_OK
        )

class LoginWithOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [BurstRateThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = AuthService.verify_otp_and_login(
            phone=serializer.validated_data['phone'],
            code=serializer.validated_data['otp'],
            role=serializer.validated_data['role']
        )
        
        return Response({
            "refresh": result['refresh'],
            "access": result['access'],
            "user": UserSerializer(result['user']).data,
            "is_new": result['is_new']
        }, status=status.HTTP_200_OK)

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

class CreateWsTicketView(APIView):
    """
    Generates a short-lived One-Time Ticket (OTT) for WebSocket connection.
    Prevents passing sensitive JWT tokens in URL query parameters.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ticket = str(uuid.uuid4())
        # Store user_id mapped to ticket with 30s expiry
        cache.set(f"ws_ticket:{ticket}", request.user.id, timeout=30)
        return Response({"ticket": ticket})