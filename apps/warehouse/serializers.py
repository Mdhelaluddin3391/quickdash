from rest_framework import serializers
from .models import PickingTask, PickItem, Location, WmsStock

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'code', 'store']

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    product_name = serializers.CharField(source='sku.product.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    
    class Meta:
        model = PickItem
        fields = ['id', 'sku_code', 'product_name', 'location_code', 'quantity_to_pick', 'status']

class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    picker_name = serializers.CharField(source='assigned_to.username', read_only=True)

    class Meta:
        model = PickingTask
        fields = ['id', 'order_id', 'status', 'assigned_to', 'picker_name', 'items', 'created_at']