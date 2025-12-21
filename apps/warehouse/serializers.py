from rest_framework import serializers

from .models import (
    Warehouse,
    ServiceArea,
    Zone,
    Bin,
    BinInventory,
    PickingTask,
    PickItem,
    PackingTask,
    DispatchRecord,
    GRN,
    GRNItem,
    PutawayTask,
    PutawayItem,
    CycleCountTask,
    CycleCountItem,
    PickSkip,
    FulfillmentCancel,
)

# ==========================
# BASIC STRUCTURE
# ==========================

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "code", "address", "lat", "lng", "is_active"]

class ServiceAreaSerializer(serializers.ModelSerializer):
    """Serializer for Service Areas with location details"""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = ServiceArea
        fields = [
            'id',
            'warehouse',
            'warehouse_name',
            'name',
            'description',
            'center_point',
            'radius_km',
            'delivery_time_minutes',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def to_representation(self, instance):
        """Convert location data to lat/lng for API response"""
        ret = super().to_representation(instance)
        if instance.center_point:
            ret['center_lat'] = instance.center_point.y
            ret['center_lng'] = instance.center_point.x
        return ret

class BinSerializer(serializers.ModelSerializer):
    zone_code = serializers.CharField(source="zone.code", read_only=True)
    warehouse_code = serializers.CharField(source="zone.warehouse.code", read_only=True)

    class Meta:
        model = Bin
        fields = ["id", "bin_code", "capacity", "zone", "zone_code", "warehouse_code"]

class BinInventorySerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    product_name = serializers.CharField(source="sku.name", read_only=True)
    warehouse_code = serializers.CharField(source="bin.zone.warehouse.code", read_only=True)
    available_qty = serializers.IntegerField(read_only=True)

    class Meta:
        model = BinInventory
        fields = [
            "id",
            "bin",
            "bin_id",
            "sku",
            "sku_id",
            "sku_code",
            "product_name",
            "warehouse_code",
            "qty",
            "reserved_qty",
            "available_qty",
        ]

# ==========================
# PICKING / PACKING
# ==========================

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    product_name = serializers.CharField(source="sku.name", read_only=True)
    bin_code = serializers.CharField(source="bin.bin_code", read_only=True)

    class Meta:
        model = PickItem
        fields = [
            "id",
            "sku",
            "sku_code",
            "product_name",
            "bin",
            "bin_code",
            "qty_to_pick",
            "picked_qty",
        ]

class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    picker_name = serializers.CharField(source="picker.full_name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = PickingTask
        fields = [
            "id",
            "order_id",
            "warehouse",
            "warehouse_code",
            "status",
            "picker",
            "picker_name",
            "items",
            "created_at",
            "completed_at",
        ]

class PackingTaskSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source="picking_task.order_id", read_only=True)
    warehouse_code = serializers.CharField(source="picking_task.warehouse.code", read_only=True)
    picker_name = serializers.CharField(source="picking_task.picker.full_name", read_only=True)
    packer_name = serializers.CharField(source="packer.full_name", read_only=True)
    
    # Nested items for UI display without extra calls
    items = serializers.SerializerMethodField()

    class Meta:
        model = PackingTask
        fields = [
            "id",
            "picking_task",
            "order_id",
            "warehouse_code",
            "status",
            "packer",
            "packer_name",
            "picker_name",
            "created_at",
            "items",
        ]

    def get_items(self, obj):
        # Retrieve items from the related picking task
        if obj.picking_task:
            return PickItemSerializer(obj.picking_task.items.all(), many=True).data
        return []

class DispatchRecordSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = DispatchRecord
        fields = [
            "id",
            "packing_task",
            "warehouse",
            "warehouse_code",
            "order_id",
            "pickup_otp",
            "status",
            "rider_id",
            "created_at",
        ]

# ==========================
# RESOLUTION
# ==========================

class PickSkipSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickSkip
        fields = [
            "id",
            "task",
            "pick_item",
            "skipped_by",
            "reason",
            "is_resolved",
            "reopen_after_scan",
            "created_at",
        ]
        read_only_fields = ["skipped_by", "is_resolved", "created_at"]

class ShortPickResolveSerializer(serializers.Serializer):
    skip_id = serializers.IntegerField()
    note = serializers.CharField(allow_blank=True)

class FulfillmentCancelSerializer(serializers.Serializer):
    pick_item_id = serializers.IntegerField()
    reason = serializers.CharField()

# ==========================
# INBOUND / PUTAWAY
# ==========================

class GRNItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    product_name = serializers.CharField(source="sku.name", read_only=True)

    class Meta:
        model = GRNItem
        fields = ["id", "sku", "sku_code", "product_name", "expected_qty", "received_qty"]

class GRNSerializer(serializers.ModelSerializer):
    items = GRNItemSerializer(many=True, read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = GRN
        fields = [
            "id",
            "grn_number",
            "warehouse",
            "warehouse_code",
            "status",
            "received_at",
            "created_by",
            "items",
        ]

class CreateGRNSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField()
    grn_number = serializers.CharField(max_length=100)
    items = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField()),
        help_text="List of {sku_id: int, qty: int}",
    )

class PutawayItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="grn_item.sku.sku_code", read_only=True)
    product_name = serializers.CharField(source="grn_item.sku.name", read_only=True)
    bin_code = serializers.CharField(source="placed_bin.bin_code", read_only=True)

    class Meta:
        model = PutawayItem
        fields = [
            "id",
            "task",
            "grn_item",
            "sku_code",
            "product_name",
            "placed_qty",
            "placed_bin",
            "bin_code",
        ]

class PutawayTaskSerializer(serializers.ModelSerializer):
    items = PutawayItemSerializer(many=True, read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = PutawayTask
        fields = [
            "id",
            "grn",
            "warehouse",
            "warehouse_code",
            "putaway_user",
            "status",
            "items",
            "created_at",
        ]

class PlacePutawaySerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    putaway_item_id = serializers.IntegerField()
    bin_id = serializers.IntegerField()
    qty_placed = serializers.IntegerField(min_value=1)

# ==========================
# CYCLE COUNT
# ==========================

class CycleCountItemSerializer(serializers.ModelSerializer):
    bin_code = serializers.CharField(source="bin.bin_code", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)

    class Meta:
        model = CycleCountItem
        fields = [
            "id",
            "task",
            "bin",
            "bin_code",
            "sku",
            "sku_code",
            "expected_qty",
            "counted_qty",
            "adjusted",
        ]

class CycleCountTaskSerializer(serializers.ModelSerializer):
    items = CycleCountItemSerializer(many=True, read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = CycleCountTask
        fields = [
            "id",
            "warehouse",
            "warehouse_code",
            "task_user",
            "status",
            "created_at",
            "items",
        ]

class CreateCycleCountSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField()
    sample_bins = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

class RecordCycleCountSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    bin_id = serializers.IntegerField()
    sku_id = serializers.IntegerField()
    counted_qty = serializers.IntegerField()

# ==========================
# DISPATCH / OTP
# ==========================

class DispatchOTPVerifySerializer(serializers.Serializer):
    dispatch_id = serializers.UUIDField()
    otp = serializers.CharField(max_length=10)