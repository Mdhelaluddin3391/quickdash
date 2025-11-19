from rest_framework import serializers
from .models import PickingTask, PickItem, Bin

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    product_name = serializers.CharField(source='sku.name', read_only=True)
    bin_code = serializers.CharField(source='bin.bin_code', read_only=True)
    
    class Meta:
        model = PickItem
        fields = ['id', 'sku_code', 'product_name', 'bin_code', 'qty_to_pick', 'picked_qty']

class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    picker_name = serializers.CharField(source='picker.username', read_only=True)

    class Meta:
        model = PickingTask
        fields = ['id', 'order_id', 'status', 'picker', 'picker_name', 'items', 'created_at']