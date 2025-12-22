from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import WarehouseInventory
from .serializers import InventorySerializer
from .services import InventoryService
from apps.warehouse.utils.warehouse_selector import get_nearest_warehouse

class StorefrontInventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for the Customer App to fetch products available in their area.
    """
    serializer_class = InventorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Requires 'lat' and 'lng' query params
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        
        if not lat or not lng:
            return WarehouseInventory.objects.none()

        warehouse = get_nearest_warehouse(lat, lng)
        if not warehouse:
            return WarehouseInventory.objects.none()
            
        return WarehouseInventory.objects.filter(
            warehouse=warehouse, 
            is_active=True,  # Assuming product active status propagates or handled in query
            quantity__gt=0
        ).select_related('product', 'product__category')

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def check_stock(self, request):
        """
        Bulk check for Cart Validation
        """
        items = request.data.get('items', []) # [{'product_id': 1, 'qty': 2}]
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        
        warehouse = get_nearest_warehouse(lat, lng)
        if not warehouse:
             return Response({"error": "No service in this area"}, status=400)

        results = []
        for item in items:
            is_available = InventoryService.check_availability(
                warehouse.id, item['product_id'], item['qty']
            )
            results.append({
                "product_id": item['product_id'],
                "available": is_available
            })
            
        return Response(results)