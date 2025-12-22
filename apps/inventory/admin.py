# apps/inventory/admin.py
from django.contrib import admin
from .models import InventoryStock, StockMovementLog

@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity', 'reserved_quantity', 'available_quantity')
    list_filter = ('warehouse',)
    search_fields = ('product__name', 'product__sku_code')
    readonly_fields = ('reserved_quantity',) # Protect integrity via UI

@admin.register(StockMovementLog)
class StockMovementLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'movement_type', 'inventory', 'quantity_change', 'reference')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('reference', 'inventory__product__sku_code')
    
    def has_add_permission(self, request):
        return False # Logs are immutable/system-generated
    
    def has_change_permission(self, request, obj=None):
        return False