# apps/inventory/serializers.py
from rest_framework import serializers
from .models import InventoryStock, InventoryHistory


class InventoryStockSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_name = serializers.CharField(source="sku.name", read_only=True)
    warehouse_name = serializers.CharField(
        source="warehouse.name", read_only=True
    )
    total_qty = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryStock
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "sku",
            "sku_code",
            "sku_name",
            "available_qty",
            "reserved_qty",
            "total_qty",
            "updated_at",
        ]


class InventoryHistorySerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    warehouse_code = serializers.CharField(
        source="warehouse.code", read_only=True
    )

    class Meta:
        model = InventoryHistory
        fields = [
            "id",
            "warehouse",
            "warehouse_code",
            "sku",
            "sku_code",
            "delta_available",
            "delta_reserved",
            "available_after",
            "reserved_after",
            "change_type",
            "reference",
            "created_at",
        ]
