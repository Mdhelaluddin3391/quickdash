from django.contrib import admin
from .models import InventoryStock

@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'sku', 'available_qty', 'reserved_qty', 'updated_at')
    search_fields = ('warehouse__name', 'sku__sku_code')