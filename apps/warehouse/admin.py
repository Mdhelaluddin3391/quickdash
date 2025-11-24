from django.contrib import admin
from .models import (
    Bin, BinInventory, PickingTask, DispatchRecord, 
    IdempotencyKey, # Existing
    # --- New Models Imported ---
    PickSkip, FulfillmentCancel, GRN, GRNItem, PutawayTask, CycleCountTask
    # ---------------------------
)

class BinInventoryInline(admin.TabularInline):
    model = BinInventory
    extra = 0

@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ('bin_code', 'capacity')
    inlines = [BinInventoryInline]

@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'picker')

@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'status', 'warehouse', 'pickup_otp')


@admin.register(IdempotencyKey) # <-- Naya Admin Register kiya
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

# ... (Existing Admin classes: BinAdmin, PickingTaskAdmin, DispatchRecordAdmin, IdempotencyKeyAdmin)