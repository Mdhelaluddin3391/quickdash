from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin # Agar map support chahiye (Optional)
from .models import (
    # --- Missing Models Added Here ---
    Warehouse, ServiceArea, Zone, Aisle, Shelf,
    # ---------------------------------
    Bin, BinInventory, PickingTask, DispatchRecord, 
    IdempotencyKey, 
    PickSkip, FulfillmentCancel, GRN, GRNItem, PutawayTask, CycleCountTask
)

# 1. Warehouse Admin Register karein
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin): # Agar map chahiye toh GISModelAdmin use karein
    list_display = ('name', 'code', 'is_active', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)

# 2. Service Area Admin Register karein
@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'warehouse', 'radius_km', 'is_active')
    list_filter = ('warehouse',)

# 3. Zone/Aisle/Shelf (Optional helper models)
@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'warehouse')

@admin.register(Aisle)
class AisleAdmin(admin.ModelAdmin):
    list_display = ('code', 'zone')

@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('code', 'aisle')

# ... Baaki purana code same rahega ...

class BinInventoryInline(admin.TabularInline):
    model = BinInventory
    extra = 0

@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ('bin_code', 'capacity', 'shelf', 'zone') # Shelf aur Zone display mein add kiya
    inlines = [BinInventoryInline]
    search_fields = ('bin_code',)

# ... PickingTask, DispatchRecord, IdempotencyKey etc... (Existing code)
@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'picker')

@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'status', 'warehouse', 'pickup_otp')

@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'route', 'response_status', 'is_expired', 'created_at')
    search_fields = ('key', 'route')
    readonly_fields = ('key', 'route', 'request_hash', 'response_status', 'response_body', 'expires_at', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 0
    readonly_fields = ('sku', 'expected_qty', 'received_qty')

@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = ('grn_number', 'warehouse', 'status', 'received_at', 'created_by')
    list_filter = ('status', 'warehouse')
    search_fields = ('grn_number',)
    inlines = [GRNItemInline]

@admin.register(PutawayTask)
class PutawayTaskAdmin(admin.ModelAdmin):
    list_display = ('grn', 'warehouse', 'status', 'putaway_user')
    list_filter = ('status', 'warehouse')

@admin.register(CycleCountTask)
class CycleCountTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'status', 'task_user', 'created_at')
    list_filter = ('status', 'warehouse')

@admin.register(PickSkip)
class PickSkipAdmin(admin.ModelAdmin):
    list_display = ('id', 'pick_item', 'skipped_by', 'reason', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'reason')

@admin.register(FulfillmentCancel)
class FulfillmentCancelAdmin(admin.ModelAdmin):
    list_display = ('id', 'pick_item', 'cancelled_by', 'reason', 'refund_initiated', 'created_at')
    list_filter = ('refund_initiated',)