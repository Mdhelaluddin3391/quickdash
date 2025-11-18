from rest_framework import serializers
from .models import InventoryStock

class InventoryStockSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    sku_name = serializers.CharField(source='sku.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = InventoryStock
        fields = [
            'id', 'warehouse', 'warehouse_name',
            'sku', 'sku_code', 'sku_name',
            'available_qty', 'reserved_qty', 'updated_at'
        ]