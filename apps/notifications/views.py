# apps/notifications/views.py
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer
from .models import FCMDevice # <-- FCMDevice import karein
from rest_framework.views import APIView # <-- Import add karein

class NotificationListView(generics.ListAPIView):
    """
    Customer ke liye saari notifications ki list.
    GET /api/v1/notifications/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        # Sirf logged-in user ki notifications dikhayenge
        return Notification.objects.filter(user=self.request.user).order_by('-sent_at')

class NotificationDetailView(generics.RetrieveAPIView):
    """
    Ek specific notification ki detail.
    GET /api/v1/notifications/<id>/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        # User sirf apni notifications dekh sakta hai
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], name='Mark as Read')
    def mark_as_read(self, request, pk=None):
        notification = get_object_or_404(Notification.objects.filter(user=request.user), pk=pk)
        
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            
        return Response({"status": "read"}, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    """POST endpoint to mark a notification as read."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        notification = get_object_or_404(Notification.objects.filter(user=request.user), pk=pk)

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])

        return Response({"status": "read"}, status=status.HTTP_200_OK)


class RegisterFCMTokenView(APIView):
    """
    Frontend app is endpoint par apna FCM Token bhejega.
    POST /api/v1/notifications/register-device/
    Body: { "fcm_token": "...", "device_type": "android" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("fcm_token")
        device_type = request.data.get("device_type", "android")

        if not token:
            return Response({"detail": "Token required"}, status=status.HTTP_400_BAD_REQUEST)

        # Update or Create logic
        device, created = FCMDevice.objects.update_or_create(
            fcm_token=token,
            defaults={
                "user": request.user,
                "device_type": device_type,
                "is_active": True
            }
        )
        
        return Response({"status": "registered", "device_id": device.id}, status=status.HTTP_200_OK)