# apps/inventory/admin.py
from django.contrib import admin
from .models import InventoryStock

@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ('sku', 'warehouse', 'available_qty', 'reserved_qty', 'updated_at')
    list_filter = ('warehouse',)
    search_fields = ('sku__sku_code', 'sku__name')
    # Read-only rakhenge taaki galti se admin se stock change na ho jaye (use Adjust API)
    readonly_fields = ('updated_at',)