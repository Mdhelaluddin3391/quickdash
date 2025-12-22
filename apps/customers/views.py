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
        """
        GET /api/v1/customers/profile/
        Returns current user's customer profile.
        """
        profile = CustomerService.get_or_create_profile(request.user)
        serializer = CustomerProfileSerializer(profile)
        return Response(serializer.data)

class AddressViewSet(viewsets.ModelViewSet):
    """
    CRUD for Addresses.
    GET/POST/PUT/DELETE /api/v1/customers/addresses/
    """
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = CustomerService.get_or_create_profile(self.request.user)
        return Address.objects.filter(customer=profile)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = CustomerService.add_address(request.user, serializer.validated_data)
        return Response(self.get_serializer(address).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        address = CustomerService.update_address(
            request.user, 
            kwargs['pk'], 
            serializer.validated_data
        )
        return Response(self.get_serializer(address).data)

    def destroy(self, request, *args, **kwargs):
        CustomerService.delete_address(request.user, kwargs['pk'])
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        """
        POST /api/v1/customers/addresses/{id}/set-default/
        """
        CustomerService.update_address(request.user, pk, {'is_default': True})
        return Response({'status': 'updated'})