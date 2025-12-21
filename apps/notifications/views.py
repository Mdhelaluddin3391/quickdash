# apps/notifications/views.py
from django.utils import timezone

from rest_framework import generics, status, views, permissions
from rest_framework.response import Response

from .models import Notification, FCMDevice, NotificationTemplate
from .serializers import (
    NotificationSerializer,
    FCMDeviceSerializer,
    NotificationTemplateSerializer,
)


class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by("-created_at")


class NotificationMarkReadView(views.APIView):
    """
    POST /api/v1/notifications/<id>/read/
    POST /api/v1/notifications/read-all/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        if pk == "read-all":
            Notification.objects.filter(
                user=request.user,
                is_read=False,
            ).update(
                is_read=True,
                read_at=timezone.now(),
            )
            return Response({"status": "all_read"})
        else:
            try:
                notif = Notification.objects.get(
                    id=pk,
                    user=request.user,
                )
            except Notification.DoesNotExist:
                return Response(
                    {"detail": "Not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            notif.mark_read()
            return Response({"status": "read"})


class FCMDeviceRegisterView(views.APIView):
    """
    Register/update FCM Device token for current user.

    POST /api/v1/notifications/devices/
    body: { "token": "...", "device_type": "android|ios|web" }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FCMDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        device_type = serializer.validated_data.get("device_type", "android")

        device, _ = FCMDevice.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "device_type": device_type,
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )

        return Response(
            FCMDeviceSerializer(device).data,
            status=status.HTTP_200_OK,
        )


class NotificationTemplateAdminViewSet(generics.ListCreateAPIView):
    """
    OPTIONAL: can be mounted behind admin permission if you want API-based template management.
    """
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAdminUser]
