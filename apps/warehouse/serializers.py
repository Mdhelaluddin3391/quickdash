from rest_framework import serializers
from .models import Warehouse, Bin, PickingTask, PickItem, PackingTask, DispatchRecord, BinInventory

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'

class BinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bin
        fields = '__all__'

class BinInventorySerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    bin_code = serializers.CharField(source='bin.code', read_only=True)
    class Meta:
        model = BinInventory
        fields = ['id', 'bin_code', 'sku_code', 'qty', 'reserved_qty']

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    bin_code = serializers.CharField(source='bin.code', read_only=True)
    class Meta:
        model = PickItem
        fields = ['id', 'sku_code', 'bin_code', 'qty', 'picked_qty']

class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    class Meta:
        model = PickingTask
        fields = ['id', 'order_id', 'status', 'items', 'created_at']

class DispatchRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispatchRecord
        fields = '__all__'