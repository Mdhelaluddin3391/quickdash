# apps/utils/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings

class ServerInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "app_name": "QuickDash",
            "version": "1.0.0",
            "debug": settings.DEBUG,
        })

class GlobalConfigView(APIView):
    """
    Frontend ko global settings (delivery fee, keys, etc.) bhejne ke liye API.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "base_delivery_fee": getattr(settings, "BASE_DELIVERY_FEE", 20.00),
            # [NEW] Razorpay Key ID bhejein taaki JS hardcoded na ho
            "razorpay_key_id": getattr(settings, "RAZORPAY_KEY_ID", ""),
        })