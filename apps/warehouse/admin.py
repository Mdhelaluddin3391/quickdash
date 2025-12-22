from django.contrib import admin
from .models import Warehouse, Zone, Bin, BinInventory, PickingTask, DispatchRecord

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name', 'code')

@admin.register(BinInventory)
class BinInventoryAdmin(admin.ModelAdmin):
    list_display = ('bin', 'sku', 'quantity')
    list_filter = ('bin__zone__warehouse',)
    search_fields = ('sku__sku_code', 'bin__bin_code')

class PickItemInline(admin.TabularInline):
    model = 'warehouse.PickItem' # String reference to avoid circular imports if any
    extra = 0

@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_id', 'status', 'picker', 'created_at')
    list_filter = ('status', 'warehouse')
    # inlines = [PickItemInline] # Enable if PickItem model is available in same context