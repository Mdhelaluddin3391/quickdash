# apps/analytics/admin.py
from django.contrib import admin
from .models import (
    DailySalesSummary,
    WarehouseKPISnapshot,
    RiderKPISnapshot,
    SKUAnalyticsDaily,
    InventorySnapshotDaily,
)


@admin.register(DailySalesSummary)
class DailySalesSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "total_orders",
        "total_paid_orders",
        "total_cancelled_orders",
        "total_revenue",
        "avg_order_value",
    )
    list_filter = ("date",)
    ordering = ("-date",)


@admin.register(WarehouseKPISnapshot)
class WarehouseKPISnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "warehouse",
        "orders_created",
        "orders_dispatched",
        "orders_delivered",
        "orders_cancelled",
    )
    list_filter = ("date", "warehouse")
    ordering = ("-date",)


@admin.register(RiderKPISnapshot)
class RiderKPISnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "rider",
        "tasks_assigned",
        "tasks_completed",
        "tasks_failed",
        "total_earnings",
    )
    list_filter = ("date",)
    ordering = ("-date",)


@admin.register(SKUAnalyticsDaily)
class SKUAnalyticsDailyAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "sku",
        "quantity_sold",
        "gross_revenue",
        "avg_selling_price",
    )
    list_filter = ("date",)
    search_fields = ("sku__sku_code", "sku__name")
    ordering = ("-date",)


@admin.register(InventorySnapshotDaily)
class InventorySnapshotDailyAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "warehouse",
        "sku",
        "closing_available_qty",
        "closing_reserved_qty",
    )
    list_filter = ("date", "warehouse")
    search_fields = ("sku__sku_code", "sku__name")
    ordering = ("-date",)
