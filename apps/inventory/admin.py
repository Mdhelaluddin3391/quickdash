# apps/inventory/admin.py
from django.contrib import admin
from .models import InventoryStock, InventoryHistory


@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "warehouse",
        "available_qty",
        "reserved_qty",
        "updated_at",
    )
    list_filter = ("warehouse",)
    search_fields = ("sku__sku_code", "sku__name")
    readonly_fields = ("updated_at",)


@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "warehouse",
        "sku",
        "delta_available",
        "delta_reserved",
        "available_after",
        "reserved_after",
        "change_type",
        "reference",
    )
    list_filter = ("warehouse", "change_type", "created_at")
    search_fields = ("sku__sku_code", "reference")
    readonly_fields = (
        "stock",
        "warehouse",
        "sku",
        "delta_available",
        "delta_reserved",
        "available_after",
        "reserved_after",
        "change_type",
        "reference",
        "created_at",
    )

    def has_add_permission(self, request):
        # History sadece system create karega
        return False

    def has_change_permission(self, request, obj=None):
        return False
