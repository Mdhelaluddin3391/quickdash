from rest_framework import serializers
from .models import InventoryStock, StockMovementLog

class InventoryStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku_code = serializers.CharField(source='product.sku_code', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = InventoryStock
        fields = [
            'id', 'warehouse_id', 'warehouse_name',
            'product_id', 'product_name', 'sku_code', 
            'quantity', 'reserved_quantity', 'available_quantity'
        ]

class StockMovementLogSerializer(serializers.ModelSerializer):
    performed_by = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = StockMovementLog
        fields = [
            'id', 'created_at', 'movement_type', 
            'quantity_change', 'balance_after', 
            'reference', 'performed_by'
        ]

class StockAdjustmentSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    delta_quantity = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)

    def validate_delta_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("Change cannot be zero.")
        return value