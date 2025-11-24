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
    Frontend ko global settings (delivery fee, etc.) bhejne ke liye API.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "base_delivery_fee": getattr(settings, "BASE_DELIVERY_FEE", 20.00),
            # Future mein aur bhi settings yahan add kar sakte hain (taxes, min_order_val etc.)
        })