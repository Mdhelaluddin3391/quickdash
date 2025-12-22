from rest_framework import serializers
from .models import WarehouseInventory
from apps.catalog.serializers import ProductSerializer

class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = WarehouseInventory
        fields = ['id', 'product', 'available_quantity', 'low_stock_threshold']