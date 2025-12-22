from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Address
from .serializers import AddressSerializer, CustomerProfileSerializer
from .services import CustomerService

class CustomerViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def profile(self, request):
        profile = CustomerService.get_or_create_profile(request.user)
        serializer = CustomerProfileSerializer(profile)
        return Response(serializer.data)

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Service layer could be used here, but for simple list access, 
        # using the profile relationship is acceptable in modular monolith
        # as long as we don't query other apps' tables.
        profile = CustomerService.get_or_create_profile(self.request.user)
        return Address.objects.filter(customer=profile)

    def create(self, request, *args, **kwargs):
        address = CustomerService.add_address(request.user, request.data)
        return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # We override update to ensure service layer logic (like default toggling) runs
        address = CustomerService.update_address(request.user, kwargs['pk'], request.data)
        return Response(AddressSerializer(address).data)