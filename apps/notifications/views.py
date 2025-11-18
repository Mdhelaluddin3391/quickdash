# apps/notifications/views.py
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer

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