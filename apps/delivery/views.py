from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import DeliveryJob
from .serializers import DeliveryJobSerializer
from .services import DeliveryService

class DeliveryJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliveryJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'rider_profile'):
            return DeliveryJob.objects.filter(rider=user)
        return DeliveryJob.objects.filter(order_id__in=user.orders.values_list('id', flat=True))

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        status_val = request.data.get('status')
        try:
            DeliveryService.update_job_status(pk, status_val, request.user)
            return Response({"status": "Updated"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)