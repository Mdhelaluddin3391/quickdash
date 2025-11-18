# apps/warehouse/serializers.py

from rest_framework import serializers
from .models import (
    Warehouse, Bin, PickingTask, PickItem, PackingTask, DispatchRecord, BinInventory,
    GRN, GRNItem, PutawayTask, PutawayItem, 
    CycleCountTask, CycleCountItem,
    PickSkip, FulfillmentCancel
)
from apps.catalog.models import SKU

# ===================================================================
#                      CORE WMS (Existing + Minor Updates)
# ===================================================================

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
        
# ===================================================================
#                      INBOUND (GRN / PUTAWAY)
# ===================================================================

class CreateGRNItemSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    qty = serializers.IntegerField(min_value=1)
    
    def validate_sku_id(self, value):
        if not SKU.objects.filter(id=value).exists():
            raise serializers.ValidationError("SKU not found.")
        return value

class CreateGRNSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    grn_number = serializers.CharField(max_length=100)
    items = CreateGRNItemSerializer(many=True)
    
class PlacePutawayItemSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    putaway_item_id = serializers.IntegerField() 
    bin_id = serializers.UUIDField()
    qty_placed = serializers.IntegerField(min_value=1)

class PutawayItemPlacedSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='grn_item.sku.sku_code', read_only=True)
    class Meta:
        model = PutawayItem
        fields = ['id', 'sku_code', 'placed_qty']


# ===================================================================
#                      PICKING RESOLUTION
# ===================================================================

class MarkPickItemSkippedSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    pick_item_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)
    reopen_for_picker = serializers.BooleanField(default=False)

class ResolveShortPickSerializer(serializers.Serializer):
    skip_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, max_length=255)
    
class FulfillmentCancelSerializer(serializers.Serializer):
    pick_item_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)

# ===================================================================
#                      CYCLE COUNT
# ===================================================================

class CreateCycleCountSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    sample_bins = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False, 
        min_length=1
    )

class RecordCycleCountSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    bin_id = serializers.UUIDField()
    sku_id = serializers.UUIDField()
    counted_qty = serializers.IntegerField(min_value=0)

class CycleCountTaskSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    class Meta:
        model = CycleCountTask
        fields = ['id', 'warehouse_code', 'status', 'created_at']

class CycleCountItemSerializer(serializers.ModelSerializer):
    bin_code = serializers.CharField(source='bin.code', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    class Meta:
        model = CycleCountItem
        fields = ['id', 'bin_code', 'sku_code', 'expected_qty', 'counted_qty', 'adjusted']