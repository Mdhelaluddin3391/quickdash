from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import OTPRequestSerializer, OTPVerifySerializer, UserProfileSerializer
from .services import AuthService

class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone = serializer.validated_data['phone_number']
        # Rate limiting should be handled via DRF Throttle classes
        
        AuthService.generate_otp(phone)
        
        return Response({
            "message": "OTP sent successfully.",
            "status": "success"
        }, status=status.HTTP_200_OK)

class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user, error = AuthService.verify_otp(
            serializer.validated_data['phone_number'],
            serializer.validated_data['otp_code'],
            serializer.validated_data['role']
        )
        
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        
        refresh = RefreshToken.for_user(user)
        # Custom claim for current role
        refresh['current_role'] = serializer.validated_data['role']
        
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserProfileSerializer(user).data
        })

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)