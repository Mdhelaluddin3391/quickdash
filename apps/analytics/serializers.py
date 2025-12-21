# apps/analytics/serializers.py
from rest_framework import serializers
from .models import (
    DailySalesSummary,
    WarehouseKPISnapshot,
    RiderKPISnapshot,
    SKUAnalyticsDaily,
    InventorySnapshotDaily,
)


class DailySalesSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySalesSummary
        fields = "__all__"


class WarehouseKPISnapshotSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = WarehouseKPISnapshot
        fields = [
            "id",
            "date",
            "warehouse",
            "warehouse_name",
            "warehouse_code",
            "orders_created",
            "orders_dispatched",
            "orders_delivered",
            "orders_cancelled",
            "avg_pick_time_seconds",
            "avg_pack_time_seconds",
            "avg_dispatch_to_delivery_seconds",
            "short_pick_incidents",
            "full_cancellations",
            "created_at",
        ]


class RiderKPISnapshotSerializer(serializers.ModelSerializer):
    rider_code = serializers.CharField(source="rider.rider_code", read_only=True)
    rider_phone = serializers.CharField(source="rider.user.phone", read_only=True)

    class Meta:
        model = RiderKPISnapshot
        fields = [
            "id",
            "date",
            "rider",
            "rider_code",
            "rider_phone",
            "tasks_assigned",
            "tasks_completed",
            "tasks_failed",
            "total_earnings",
            "avg_delivery_time_seconds",
            "created_at",
        ]


class SKUAnalyticsDailySerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_name = serializers.CharField(source="sku.name", read_only=True)

    class Meta:
        model = SKUAnalyticsDaily
        fields = [
            "id",
            "date",
            "sku",
            "sku_code",
            "sku_name",
            "quantity_sold",
            "gross_revenue",
            "avg_selling_price",
            "orders_count",
            "refunds_count",
            "refunded_quantity",
            "created_at",
        ]


class InventorySnapshotDailySerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_name = serializers.CharField(source="sku.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = InventorySnapshotDaily
        fields = [
            "id",
            "date",
            "warehouse",
            "warehouse_name",
            "warehouse_code",
            "sku",
            "sku_code",
            "sku_name",
            "closing_available_qty",
            "closing_reserved_qty",
            "created_at",
        ]
