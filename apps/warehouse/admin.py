from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin  # FIX: Django 5 Compatible
from django.contrib import messages
from django.db import transaction

from .models import (
    Warehouse, ServiceArea, Zone, Aisle, Shelf, Bin, BinInventory,
    StockMovement, PickingTask, PickItem, PackingTask, DispatchRecord, 
    GRN, GRNItem, PutawayTask, PutawayItem, CycleCountTask, CycleCountItem,
    IdempotencyKey, PickSkip, ShortPickIncident, FulfillmentCancel
)

# --- Inlines for Structure ---
class ServiceAreaInline(admin.StackedInline):
    model = ServiceArea
    extra = 0

class ZoneInline(admin.TabularInline):
    model = Zone
    extra = 0

class AisleInline(admin.TabularInline):
    model = Aisle
    extra = 0

class ShelfInline(admin.TabularInline):
    model = Shelf
    extra = 0

class BinInline(admin.TabularInline):
    model = Bin
    extra = 0

# --- Inlines for Tasks ---
class PickItemInline(admin.TabularInline):
    model = PickItem
    extra = 0
    readonly_fields = ('sku', 'bin', 'qty_to_pick', 'picked_qty')
    can_delete = False

class PutawayItemInline(admin.TabularInline):
    model = PutawayItem
    extra = 0
    readonly_fields = ('grn_item', 'placed_qty', 'placed_bin')

class CycleCountItemInline(admin.TabularInline):
    model = CycleCountItem
    extra = 0
    readonly_fields = ('bin', 'sku', 'expected_qty', 'counted_qty', 'adjusted')

class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 0

class BinInventoryInline(admin.TabularInline):
    model = BinInventory
    extra = 0

# ============================================
# Physical Structure Admin
# ============================================

@admin.register(Warehouse)
class WarehouseAdmin(GISModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name', 'code')

@admin.register(ServiceArea)
class ServiceAreaAdmin(GISModelAdmin):
    list_display = ('name', 'warehouse', 'is_active', 'delivery_time_minutes')
    list_filter = ('warehouse', 'is_active')
    search_fields = ('name',)

# FIX: Removed duplicate admin.site.register() calls causing the crash.
# The @admin.register decorators below handle registration automatically.

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'warehouse')
    list_filter = ('warehouse',)
    inlines = [AisleInline]

@admin.register(Aisle)
class AisleAdmin(admin.ModelAdmin):
    list_display = ('code', 'zone')
    list_filter = ('zone__warehouse',)
    inlines = [ShelfInline]

@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('code', 'aisle')
    inlines = [BinInline]

@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ('bin_code', 'shelf', 'capacity')
    search_fields = ('bin_code',)
    inlines = [BinInventoryInline]

# ============================================
# Inventory & Movements (Audit)
# ============================================

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'sku', 'warehouse', 'movement_type', 'qty_change', 'performed_by')
    list_filter = ('movement_type', 'warehouse', 'timestamp')
    search_fields = ('sku__sku_code', 'reference_id')
    readonly_fields = ('sku', 'warehouse', 'bin', 'qty_change', 'movement_type', 'reference_id', 'timestamp', 'performed_by')
    list_select_related = ('sku', 'warehouse', 'performed_by')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# ============================================
# Operational Tasks
# ============================================

@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'picker', 'created_at')
    list_filter = ('status', 'warehouse')
    search_fields = ('order_id', 'picker__phone')
    inlines = [PickItemInline]

@admin.register(PackingTask)
class PackingTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_order_id', 'status', 'packer', 'created_at')
    list_filter = ('status',)
    
    def get_order_id(self, obj):
        return obj.picking_task.order_id
    get_order_id.short_description = 'Order ID'

@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'status', 'warehouse', 'rider_id', 'pickup_otp')
    list_filter = ('status', 'warehouse')
    search_fields = ('order_id', 'rider_id')

@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = ('grn_number', 'warehouse', 'status', 'received_at')
    list_filter = ('status', 'warehouse')
    inlines = [GRNItemInline]
    actions = ['process_grn_stock']

    @admin.action(description='✅ Receive Stock (Update Inventory)')
    def process_grn_stock(self, request, queryset):
        count = 0
        for grn in queryset:
            if grn.status == 'received':
                self.message_user(request, f"GRN {grn.grn_number} is already received!", level=messages.WARNING)
                continue

            target_bin = Bin.objects.filter(shelf__aisle__zone__warehouse=grn.warehouse).first()
            
            if not target_bin:
                self.message_user(request, f"Error: No BIN found in {grn.warehouse.name}! Please create structure first.", level=messages.ERROR)
                continue

            with transaction.atomic():
                for item in grn.items.all():
                    qty_to_add = item.received_qty if item.received_qty > 0 else item.expected_qty
                    
                    inventory, created = BinInventory.objects.get_or_create(
                        bin=target_bin,
                        sku=item.sku,
                        defaults={'qty': 0}
                    )
                    
                    inventory.qty += qty_to_add
                    inventory.save()

                    StockMovement.objects.create(
                        sku=item.sku,
                        warehouse=grn.warehouse,
                        bin=target_bin,
                        qty_change=qty_to_add,
                        movement_type='INWARD',
                        reference_id=grn.grn_number,
                        performed_by=request.user
                    )

                grn.status = 'received'
                grn.save()
                count += 1

        if count > 0:
            self.message_user(request, f"Successfully processed {count} GRNs. Stock updated!")

@admin.register(PutawayTask)
class PutawayTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'grn', 'status', 'putaway_user')
    list_filter = ('status',)
    inlines = [PutawayItemInline]

@admin.register(CycleCountTask)
class CycleCountTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [CycleCountItemInline]

# ============================================
# Exceptions & Incidents
# ============================================

@admin.register(PickSkip)
class PickSkipAdmin(admin.ModelAdmin):
    list_display = ('id', 'pick_item', 'reason', 'is_resolved')
    list_filter = ('is_resolved', 'reason')

@admin.register(ShortPickIncident)
class ShortPickIncidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_picked_qty', 'resolved_by', 'created_at')

@admin.register(FulfillmentCancel)
class FulfillmentCancelAdmin(admin.ModelAdmin):
    list_display = ('id', 'reason', 'cancelled_by', 'refund_initiated')
    list_filter = ('refund_initiated',)

@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'route', 'response_status', 'created_at')
    search_fields = ('key',)
    readonly_fields = [field.name for field in IdempotencyKey._meta.fields]
    
    def has_add_permission(self, request):
        return False