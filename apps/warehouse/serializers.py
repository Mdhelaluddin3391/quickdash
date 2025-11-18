from rest_framework import serializers

from apps.warehouse.models import (
    Warehouse, Zone, Aisle, Shelf, Bin,
    PickingTask, PickItem, PackingTask, PackingItem,
    DispatchRecord, PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem,
    # FIX: Import BinInventory here
    BinInventory
)
from apps.inventory.models import SKU, InventoryStock
# --------- Basic structure --------- #

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "code", "address", "lat", "lng", "is_active"]


class ZoneSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Zone
        fields = ["id", "warehouse", "warehouse_code", "code", "name"]


class AisleSerializer(serializers.ModelSerializer):
    zone_code = serializers.CharField(source="zone.code", read_only=True)

    class Meta:
        model = Aisle
        fields = ["id", "zone", "zone_code", "code"]


class ShelfSerializer(serializers.ModelSerializer):
    aisle_code = serializers.CharField(source="aisle.code", read_only=True)

    class Meta:
        model = Shelf
        fields = ["id", "aisle", "aisle_code", "code"]


class BinSerializer(serializers.ModelSerializer):
    shelf_code = serializers.CharField(source="shelf.code", read_only=True)
    warehouse_id = serializers.UUIDField(source="shelf.aisle.zone.warehouse.id", read_only=True)
    warehouse_code = serializers.CharField(source="shelf.aisle.zone.warehouse.code", read_only=True)

    class Meta:
        model = Bin
        fields = [
            "id", "code", "bin_type", "is_active",
            "shelf", "shelf_code", "warehouse_id", "warehouse_code",
        ]


# --------- Inventory serializers --------- #

class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ["id", "sku_code", "name", "unit", "is_active", "metadata"]


class BinInventorySerializer(serializers.ModelSerializer):
    bin_code = serializers.CharField(source="bin.code", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)

    class Meta:
        model = BinInventory
        fields = ["id", "bin", "bin_code", "sku", "sku_code", "qty", "reserved_qty"]


class InventoryStockSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)

    class Meta:
        model = InventoryStock
        fields = [
            "id",
            "warehouse",
            "warehouse_code",
            "sku",
            "sku_code",
            "available_qty",
            "reserved_qty",
        ]


# --------- Picking --------- #

class PickItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True)
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = PickItem
        fields = [
            "id",
            "task",
            "sku",
            "sku_code",
            "bin",
            "bin_code",
            "qty",
            "picked_qty",
            "remaining",
            "scanned_at",
        ]


class PickingTaskSerializer(serializers.ModelSerializer):
    items = PickItemSerializer(many=True, read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = PickingTask
        fields = [
            "id",
            "order_id",
            "warehouse",
            "warehouse_code",
            "picker",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "note",
            "items",
        ]


# --------- Packing --------- #

class PackingItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)

    class Meta:
        model = PackingItem
        fields = ["id", "packing_task", "sku", "sku_code", "qty", "packed_qty"]


class PackingTaskSerializer(serializers.ModelSerializer):
    items = PackingItemSerializer(many=True, read_only=True)
    order_id = serializers.CharField(source="picking_task.order_id", read_only=True)
    warehouse_id = serializers.UUIDField(source="picking_task.warehouse.id", read_only=True)

    class Meta:
        model = PackingTask
        fields = [
            "id",
            "picking_task",
            "order_id",
            "warehouse_id",
            "packer",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "total_weight_kg",
            "note",
            "items",
        ]


# --------- Dispatch --------- #

class DispatchRecordSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = DispatchRecord
        fields = [
            "id",
            "order_id",
            "warehouse",
            "warehouse_code",
            "packing_task",
            "status",
            "rider_id",
            "pickup_otp",
            "created_at",
            "picked_up_at",
            "delivered_at",
            "failed_reason",
        ]


# --------- Exceptions info --------- #

class PickSkipSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickSkip
        fields = ["id", "pick_item", "picker", "reason", "skipped_at", "reopened"]


class ShortPickIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortPickIncident
        fields = [
            "id",
            "pick_item",
            "reported_by",
            "status",
            "reported_at",
            "resolved_by",
            "resolved_at",
            "note",
        ]


class FulfillmentCancelSerializer(serializers.ModelSerializer):
    class Meta:
        model = FulfillmentCancel
        fields = ["id", "pick_item", "admin", "reason", "created_at"]


# --------- GRN / Putaway --------- #

class GRNSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = GRN
        fields = [
            "id",
            "grn_no",
            "warehouse",
            "warehouse_code",
            "received_at",
            "created_by",
            "metadata",
            "status",
        ]


class PutawayItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, default=None)

    class Meta:
        model = PutawayItem
        fields = [
            "id",
            "task",
            "sku",
            "sku_code",
            "expected_qty",
            "bin",
            "bin_code",
            "placed_qty",
            "placed_at",
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
            "assigned_to",
            "created_at",
            "started_at",
            "completed_at",
            "status",
            "items",
        ]


# --------- Cycle count --------- #

class CycleCountItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True)

    class Meta:
        model = CycleCountItem
        fields = [
            "id",
            "cycle_task",
            "bin",
            "bin_code",
            "sku",
            "sku_code",
            "expected_qty",
            "counted_qty",
            "counted_at",
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
            "created_by",
            "created_at",
            "scheduled_for",
            "completed_at",
            "note",
            "items",
        ]
