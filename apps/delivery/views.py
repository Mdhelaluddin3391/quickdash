from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsRider

from .models import DeliveryTask
from .serializers import DeliveryTaskSerializer, OTPVerificationSerializer
from .services import DeliveryService

class DeliveryTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Rider API for managing deliveries.
    """
    serializer_class = DeliveryTaskSerializer
    permission_classes = [IsAuthenticated, IsRider]

    def get_queryset(self):
        # Only show tasks assigned to the logged-in rider
        return DeliveryTask.objects.filter(rider__user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        try:
            DeliveryService.rider_accept_task(pk, request.user)
            return Response({"status": "Accepted"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def pickup(self, request, pk=None):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            DeliveryService.process_pickup(pk, request.user, serializer.validated_data['otp'])
            return Response({"status": "Picked Up"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            DeliveryService.complete_delivery(pk, request.user, serializer.validated_data['otp'])
            return Response({"status": "Delivered"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)