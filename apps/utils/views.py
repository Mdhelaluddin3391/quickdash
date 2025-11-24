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
