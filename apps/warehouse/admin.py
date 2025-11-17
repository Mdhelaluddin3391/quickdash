# apps/warehouse/admin.py

from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from .services import admin_fulfillment_cancel
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

from apps.inventory.models import (
    SKU, BinInventory, InventoryStock, StockMovement
)

from .services import admin_fulfillment_cancel
from .tasks import send_refund_webhook


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
    list_display = ('shelf', 'code', 'preferred_sku', 'capacity')


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
    list_display = ('pick_item', 'picker', 'skipped_at', 'resolved')


@admin.register(ShortPickIncident)
class ShortPickIncidentAdmin(admin.ModelAdmin):
    list_display = ('pick_item', 'created_at', 'status')


@admin.register(FulfillmentCancel)
class FulfillmentCancelAdmin(admin.ModelAdmin):
    list_display = ('pick_item', 'admin', 'created_at')


# -----------------------------------------------------------
# PACKING
# -----------------------------------------------------------
@admin.register(PackingTask)
class PackingTaskAdmin(admin.ModelAdmin):
    list_display = ('picking_task', 'status', 'packer', 'created_at', 'packed_at')


@admin.register(PackingItem)
class PackingItemAdmin(admin.ModelAdmin):
    list_display = ('packing_task', 'sku', 'qty')


# -----------------------------------------------------------
# DISPATCH
# -----------------------------------------------------------
@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'courier', 'assigned_at', 'picked_up_at', 'delivered_at')
    list_filter = ('status', 'courier')


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
    list_display = ('putaway_task', 'sku', 'qty', 'suggested_bin', 'placed_bin', 'placed_qty')


# -----------------------------------------------------------
# CYCLE COUNT
# -----------------------------------------------------------
@admin.register(CycleCountTask)
class CycleCountTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'status', 'created_at')


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
            fc = admin_fulfillment_cancel(pi, request.user, reason="Admin bulk FC")

            payload = {
                'order_id': pi.task.order_id,
                'pick_item_id': str(pi.id),
                'sku_id': str(pi.sku_id),
                'qty': remaining,
                'reason': 'Fulfillment canceled by admin',
            }

            send_refund_webhook.delay(str(fc.id), payload)

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
