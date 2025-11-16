# apps/warehouse/serializers.py

from rest_framework import serializers

# -----------------------------------------------------------
# IMPORT MODELS
# -----------------------------------------------------------
from apps.warehouse.models import (
    Warehouse, Zone, Aisle, Shelf, Bin,
    PickingTask, PickItem, PackingTask, PackingItem,
    DispatchRecord, PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem
)

from apps.inventory.models import SKU, BinInventory, InventoryStock


# -----------------------------------------------------------
# BASIC STRUCTURE SERIALIZERS
# -----------------------------------------------------------
class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'


class AisleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aisle
        fields = '__all__'


class ShelfSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shelf
        fields = '__all__'


class BinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bin
        fields = '__all__'


# -----------------------------------------------------------
# INVENTORY SERIALIZERS
# -----------------------------------------------------------
class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = '__all__'


class BinInventorySerializer(serializers.ModelSerializer):
    sku = SKUSerializer(read_only=True)

    class Meta:
        model = BinInventory
        fields = ['id', 'bin', 'sku', 'qty', 'reserved_qty', 'updated_at']


class InventoryStockSerializer(serializers.ModelSerializer):
    sku = SKUSerializer(read_only=True)

    class Meta:
        model = InventoryStock
        fields = ['id', 'warehouse', 'sku', 'available_qty', 'reserved_qty', 'updated_at']


# -----------------------------------------------------------
# PICK / SKIP / SHORT PICK / FC SERIALIZERS
# -----------------------------------------------------------
class PickSkipSerializer(serializers.ModelSerializer):
    picker_username = serializers.CharField(source='picker.username', read_only=True)

    class Meta:
        model = PickSkip
        fields = [
            'id', 'pick_item', 'picker', 'picker_username', 'reason',
            'skipped_at', 'reopen_after_scan', 'resolved',
            'resolved_by', 'resolved_at', 'resolution_note'
        ]


class ShortPickIncidentSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ShortPickIncident
        fields = [
            'id', 'pick_item', 'created_at', 'created_by',
            'created_by_username', 'status', 'note'
        ]


class FulfillmentCancelSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source='admin.username', read_only=True)

    class Meta:
        model = FulfillmentCancel
        fields = [
            'id', 'pick_item', 'admin', 'admin_username',
            'reason', 'created_at'
        ]


# -----------------------------------------------------------
# PICKING SERIALIZERS
# -----------------------------------------------------------
class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    bin_code = serializers.CharField(source='bin.code', read_only=True)
    skip = serializers.SerializerMethodField()

    class Meta:
        model = PickItem
        fields = [
            'id', 'sku', 'sku_code', 'bin', 'bin_code',
            'qty', 'picked_qty', 'scanned_at', 'skip'
        ]

    def get_skip(self, obj):
        skip = getattr(obj, 'skip', None)
        if not skip:
            return None
        return {
            'skip_id': str(skip.id),
            'skipped_at': skip.skipped_at,
            'reason': skip.reason,
            'resolved': skip.resolved,
            'reopen_after_scan': skip.reopen_after_scan,
        }


class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    picker_username = serializers.CharField(source='picker.username', read_only=True)

    class Meta:
        model = PickingTask
        fields = [
            'id', 'order_id', 'warehouse', 'picker', 'picker_username',
            'status', 'created_at', 'started_at', 'completed_at',
            'items', 'note'
        ]


# -----------------------------------------------------------
# PACKING SERIALIZERS
# -----------------------------------------------------------
class PackingItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)

    class Meta:
        model = PackingItem
        fields = ['id', 'sku', 'sku_code', 'qty']


class PackingTaskSerializer(serializers.ModelSerializer):
    items = PackingItemSerializer(many=True, read_only=True)
    packer_username = serializers.CharField(source='packer.username', read_only=True)

    class Meta:
        model = PackingTask
        fields = [
            'id', 'picking_task', 'packer', 'packer_username',
            'status', 'created_at', 'packed_at',
            'package_label', 'items'
        ]


# -----------------------------------------------------------
# DISPATCH SERIALIZER
# -----------------------------------------------------------
class DispatchRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispatchRecord
        fields = '__all__'


# -----------------------------------------------------------
# PUTAWAY SERIALIZERS
# -----------------------------------------------------------
class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = '__all__'


class PutawayItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    suggested_bin_code = serializers.CharField(source='suggested_bin.code', read_only=True)
    placed_bin_code = serializers.CharField(source='placed_bin.code', read_only=True)

    class Meta:
        model = PutawayItem
        fields = [
            'id', 'sku', 'sku_code', 'qty',
            'suggested_bin', 'suggested_bin_code',
            'placed_bin', 'placed_bin_code',
            'placed_qty'
        ]


class PutawayTaskSerializer(serializers.ModelSerializer):
    items = PutawayItemSerializer(many=True, read_only=True)

    class Meta:
        model = PutawayTask
        fields = [
            'id', 'grn', 'warehouse', 'status',
            'created_at', 'completed_at', 'items'
        ]


# -----------------------------------------------------------
# CYCLE COUNT SERIALIZERS
# -----------------------------------------------------------
class CycleCountItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    bin_code = serializers.CharField(source='bin.code', read_only=True)

    class Meta:
        model = CycleCountItem
        fields = [
            'id', 'cycle_task', 'bin', 'bin_code',
            'sku', 'sku_code', 'expected_qty',
            'counted_qty', 'counted_at', 'adjusted'
        ]
