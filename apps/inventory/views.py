# apps/inventory/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsWarehouseManagerEmployee, IsEmployee
from .models import InventoryStock
from .serializers import InventoryStockSerializer
from apps.catalog.models import SKU
from apps.warehouse.models import Warehouse

class InventoryListAPIView(generics.ListAPIView):
    """
    Employees ke liye stock check karne ki API.
    Filters: ?warehouse_id=...&sku_code=...
    GET /api/v1/inventory/stock/ 
    """
    permission_classes = [IsAuthenticated, IsEmployee]
    serializer_class = InventoryStockSerializer

    def get_queryset(self):
        queryset = InventoryStock.objects.select_related('sku', 'warehouse').all()
        
        warehouse_id = self.request.query_params.get('warehouse_id')
        sku_code = self.request.query_params.get('sku_code')
        low_stock = self.request.query_params.get('low_stock') # e.g., true

        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if sku_code:
            queryset = queryset.filter(sku__sku_code=sku_code)
        if low_stock == 'true':
            queryset = queryset.filter(available_qty__lte=10) # Alert for items < 10
            
        return queryset

class AdjustStockAPIView(APIView):
    """
    Direct manual adjustment (Emergency/Admin use).
    POST /api/v1/inventory/adjust/ 
    """
    # WARNING: This view directly modifies the InventoryStock and can cause data inconsistency
    # with the BinInventory. A better approach would be to create a StockMovement record
    # with a movement type of 'ADJUSTMENT' and then trigger a sync.
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]

    def post(self, request):
        sku_id = request.data.get('sku_id')
        warehouse_id = request.data.get('warehouse_id')
        quantity = request.data.get('quantity') # Kitna add/subtract karna hai (+10 ya -5)
        
        if not all([sku_id, warehouse_id, quantity]):
            return Response({"detail": "sku_id, warehouse_id, and quantity required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            quantity = int(quantity)
            
            # Stock fetch ya create karo
            stock, created = InventoryStock.objects.get_or_create(
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                defaults={'available_qty': 0}
            )
            
            # Adjustment logic
            stock.available_qty += quantity
            if stock.available_qty < 0:
                return Response({"detail": "Stock cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)
                
            stock.save()
            
            return Response({
                "message": "Stock adjusted successfully", 
                "new_available_qty": stock.available_qty
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({"detail": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)