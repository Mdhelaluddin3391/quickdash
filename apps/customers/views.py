from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Address
from .serializers import AddressSerializer
from .services import CustomerService

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optimized query with profile join
        return Address.objects.filter(
            customer__user=self.request.user
        ).order_by("-is_default", "-created_at")

    def perform_destroy(self, instance):
        # Prevent deleting the last address if it's default? 
        # For MVP, allow deletion.
        instance.delete()

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        try:
            CustomerService.set_default_address(request.user, pk)
            return Response({"status": "Address set as default"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)