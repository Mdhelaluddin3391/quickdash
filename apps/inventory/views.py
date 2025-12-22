# apps/inventory/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.utils.permissions import IsStaffOrReadOnly

from .models import InventoryStock
from .serializers import InventoryStockSerializer
from .services import InventoryService

class InventoryStockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View for Warehouse Managers/Staff to monitor stock levels.
    Not for public consumption (Public uses Catalog with Availability check).
    """
    queryset = InventoryStock.objects.all()
    serializer_class = InventoryStockSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['warehouse_id', 'product__category']
    search_fields = ['product__name', 'product__sku_code']

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        Report: Items below threshold.
        """
        warehouse_id = request.query_params.get('warehouse_id')
        if not warehouse_id:
            return Response({"error": "Warehouse ID required"}, status=400)
            
        # Using F expression for db-level comparison
        from django.db.models import F
        stocks = InventoryStock.objects.filter(
            warehouse_id=warehouse_id,
            quantity__lte=F('low_stock_threshold')
        )
        
        page = self.paginate_queryset(stocks)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)