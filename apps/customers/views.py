# apps/customers/views.py

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Address
from .serializers import AddressSerializer
from .services import CustomerService


class AddressViewSet(ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = CustomerService.get_profile(self.request.user)
        return Address.objects.filter(customer=profile)

    def perform_create(self, serializer):
        profile = CustomerService.get_profile(self.request.user)
        serializer.save(customer=profile)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        CustomerService.set_default_address(request.user, pk)
        return Response({"status": "default_updated"})
