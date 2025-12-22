# apps/inventory/serializers.py
from rest_framework import serializers
from .models import InventoryStock, StockMovementLog

class InventoryStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku_code = serializers.CharField(source='product.sku_code', read_only=True)
    
    class Meta:
        model = InventoryStock
        fields = [
            'id', 'product_id', 'product_name', 'sku_code', 
            'quantity', 'reserved_quantity', 'available_quantity'
        ]

class StockMovementLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovementLog
        fields = '__all__'