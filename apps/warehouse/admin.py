# apps/warehouse/admin.py

from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
# FIX: Sahi function ka naam import kiya
from .services import create_fulfillment_cancel
from .tasks import send_refund_webhook
from apps.warehouse.models import (
    Warehouse, Zone, Aisle, Shelf, Bin,
    PickingTask, PickItem, PickSkip, ShortPickIncident, FulfillmentCancel,
    PackingTask, PackingItem,
    DispatchRecord,
    GRN, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem,
    IdempotencyKey
)
from .tasks import process_admin_refund_task # <-- Updated import
from apps.inventory.models import (
    SKU, BinInventory, InventoryStock, StockMovement
)

# FIX: Duplicate import ko hata diya


# -----------------------------------------------------------
# BASIC STRUCTURE
# -----------------------------------------------------------
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'created_at')
    search_fields = ('code', 'name')


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'code', 'name')


@admin.register(Aisle)
class AisleAdmin(admin.ModelAdmin):
    list_display = ('zone', 'code')


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('aisle', 'code')


@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    # FIX: 'preferred_sku' aur 'capacity' fields aapke naye Bin model mein nahi hain.
    #
    # Isko naye fields se update kar diya hai.
    list_display = ('shelf', 'code', 'bin_type', 'is_active')


# -----------------------------------------------------------
# INVENTORY
# -----------------------------------------------------------
@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'name', 'unit', 'is_active')


@admin.register(BinInventory)
class BinInventoryAdmin(admin.ModelAdmin):
    list_display = ('bin', 'sku', 'qty', 'reserved_qty', 'updated_at')


@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'sku', 'available_qty', 'reserved_qty', 'updated_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('sku', 'warehouse', 'bin', 'change_type', 'delta_qty', 'created_at')
    list_filter = ('change_type', 'warehouse')


# -----------------------------------------------------------
# PICKING / SKIP / SHORT-PICK
# -----------------------------------------------------------
@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'picker', 'created_at', 'started_at', 'completed_at')
    search_fields = ('order_id',)


@admin.register(PickSkip)
class PickSkipAdmin(admin.ModelAdmin):
    # FIX: 'resolved' field aapke naye PickSkip model mein nahi hai.
    #
    # Isko 'reopened' se badal diya hai.
    list_display = ('pick_item', 'picker', 'skipped_at', 'reopened')


@admin.register(ShortPickIncident)
class ShortPickIncidentAdmin(admin.ModelAdmin):
    # FIX: 'created_at' field ka naam 'reported_at' hai.
    #
    list_display = ('pick_item', 'reported_at', 'status')


@admin.register(FulfillmentCancel)
class FulfillmentCancelAdmin(admin.ModelAdmin):
    list_display = ('pick_item', 'admin', 'created_at')


# -----------------------------------------------------------
# PACKING
# -----------------------------------------------------------
@admin.register(PackingTask)
class PackingTaskAdmin(admin.ModelAdmin):
    # FIX: 'packed_at' field ka naam 'completed_at' hai.
    #
    list_display = ('picking_task', 'status', 'packer', 'created_at', 'completed_at')


@admin.register(PackingItem)
class PackingItemAdmin(admin.ModelAdmin):
    list_display = ('packing_task', 'sku', 'qty')


# -----------------------------------------------------------
# DISPATCH
# -----------------------------------------------------------
@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    # FIX: 'courier' ko 'rider_id' se aur 'assigned_at' ko 'created_at' se badal diya hai.
    #
    list_display = ('order_id', 'warehouse', 'status', 'rider_id', 'created_at', 'picked_up_at', 'delivered_at')
    list_filter = ('status', 'rider_id') # FIX: 'courier' ko 'rider_id' se badla


# -----------------------------------------------------------
# PUTAWAY
# -----------------------------------------------------------
@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = ('grn_no', 'warehouse', 'received_at', 'status')


@admin.register(PutawayTask)
class PutawayTaskAdmin(admin.ModelAdmin):
    list_display = ('grn', 'warehouse', 'status', 'created_at')


@admin.register(PutawayItem)
class PutawayItemAdmin(admin.ModelAdmin):
    # FIX: Model fields se match karne ke liye update kiya.
    #
    list_display = ('task', 'sku', 'expected_qty', 'bin', 'placed_qty')


# -----------------------------------------------------------
# CYCLE COUNT
# -----------------------------------------------------------
@admin.register(CycleCountTask)
class CycleCountTaskAdmin(admin.ModelAdmin):
    # FIX: 'status' field model mein nahi hai, use 'completed_at' se badal diya.
    #
    list_display = ('id', 'warehouse', 'created_at', 'completed_at', 'scheduled_for')


@admin.register(CycleCountItem)
class CycleCountItemAdmin(admin.ModelAdmin):
    list_display = ('cycle_task', 'bin', 'sku', 'expected_qty', 'counted_qty', 'adjusted')


# -----------------------------------------------------------
# IDEMPOTENCY KEYS
# -----------------------------------------------------------
@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'route', 'created_at', 'expires_at')
    search_fields = ('key', 'route')


# -----------------------------------------------------------
# CUSTOM FC BULK ACTION
# -----------------------------------------------------------
@admin.action(description='Mark selected pick items as FC and trigger refund webhook')
def mark_fc_action(modeladmin, request, queryset):
    for pi in queryset:
        remaining = pi.qty - pi.picked_qty
        if remaining <= 0:
            modeladmin.message_user(request,
                f"PickItem {pi.id}: no quantity left to cancel.",
                level=messages.WARNING)
            continue

        try:
            # FIX: Sahi function ka naam aur parameter (pi.id) use kiya
            fc = create_fulfillment_cancel(pi.id, request.user, reason="Admin bulk FC")

            process_admin_refund_task.delay(
                order_id=pi.task.order_id,
                # Hum abhi specific amount nahi bhej rahe, internal logic handle karega
                # Ya aap chaho to amount calculate karke bhej sakte ho
                reason=f'Fulfillment canceled for Item {pi.sku.sku_code}'
            )

            modeladmin.message_user(request,
                f"FC + refund queued for PickItem {pi.id}",
                level=messages.SUCCESS)

        except Exception as e:
            modeladmin.message_user(request,
                f"Failed for PickItem {pi.id}: {e}",
                level=messages.ERROR)


@admin.register(PickItem)
class PickItemAdmin(admin.ModelAdmin):
    list_display = ('task', 'sku', 'bin', 'qty', 'picked_qty')
    actions = [mark_fc_action]