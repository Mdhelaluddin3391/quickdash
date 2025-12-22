from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.utils.permissions import IsStaffOrReadOnly
from django.db.models import F

from .models import InventoryStock, StockMovementLog
from .serializers import (
    InventoryStockSerializer, 
    StockMovementLogSerializer, 
    StockAdjustmentSerializer
)
from .services import InventoryService

class InventoryStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryStock.objects.select_related('product', 'warehouse').all()
    serializer_class = InventoryStockSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['warehouse_id', 'product__category']
    search_fields = ['product__name', 'product__sku_code']

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        warehouse_id = request.query_params.get('warehouse_id')
        if not warehouse_id:
            return Response({"error": "Warehouse ID required"}, status=400)
            
        stocks = self.queryset.filter(
            warehouse_id=warehouse_id,
            quantity__lte=F('low_stock_threshold')
        )
        
        page = self.paginate_queryset(stocks)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

class InventoryHistoryListAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def get(self, request):
        qs = StockMovementLog.objects.select_related('inventory__product').all()
        # Filters
        if sku := request.query_params.get('sku_code'):
            qs = qs.filter(inventory__product__sku_code=sku)
        if wh := request.query_params.get('warehouse_id'):
            qs = qs.filter(inventory__warehouse_id=wh)
            
        qs = qs[:100] # Limit for performance
        data = StockMovementLogSerializer(qs, many=True).data
        return Response(data)

class AdjustStockAPIView(views.APIView):
    """
    Manual override for Warehouse Managers.
    """
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        d = serializer.validated_data
        try:
            InventoryService.manual_adjustment(
                warehouse_id=d['warehouse_id'],
                product_id=d['product_id'],
                delta_qty=d['delta_quantity'],
                user=request.user,
                reason=d['reason']
            )
            return Response({"status": "Adjustment recorded"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)