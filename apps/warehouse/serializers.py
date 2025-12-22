from rest_framework import serializers
from .models import PickingTask, PackingTask, DispatchRecord, PickItem, Warehouse

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'code', 'address']

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    bin_code = serializers.CharField(source='bin.bin_code', read_only=True)
    
    class Meta:
        model = PickItem
        fields = ['id', 'sku_code', 'bin_code', 'qty_to_pick', 'picked_qty', 'is_picked']

class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = PickingTask
        fields = ['id', 'order_id', 'status', 'items', 'created_at']

class PackingTaskSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source='picking_task.order_id', read_only=True)
    
    class Meta:
        model = PackingTask
        fields = ['id', 'order_id', 'status', 'created_at']

class DispatchRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispatchRecord
        fields = ['id', 'order_id', 'status', 'pickup_otp']

class ScanPickSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    pick_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)