import random
from django.db import transaction
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import EmployeeProfile
from .models import (
    Warehouse, Bin, BinInventory, StockMovement, 
    PickingTask, PickItem, PackingTask, DispatchRecord,
    PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, GRNItem, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem
)
# NOTE: Ensure apps/warehouse/signals.py exists and has these signals defined!
from .signals import inventory_change_required, dispatch_ready_for_delivery, item_fulfillment_cancelled

# =========================================================
# OUTBOUND (PICKING & PACKING)
# =========================================================

@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items_needed):
    """
    GREEDY ALLOCATION LOGIC:
    Locks stock across multiple bins to fulfill an order.
    """
    warehouse = Warehouse.objects.get(id=warehouse_id)
    task = PickingTask.objects.create(order_id=str(order_id), warehouse=warehouse, status='PENDING')

    for item in items_needed:
        sku_id = item['sku_id']
        qty_needed = int(item['qty'])
        
        # 1. Find bins with stock, prioritize largest piles (Greedy)
        available_bins = BinInventory.objects.select_for_update().select_related('bin__zone__warehouse').filter(
            bin__zone__warehouse=warehouse,
            sku_id=sku_id,
            qty__gt=F('reserved_qty')
        ).order_by('-qty')

        qty_remaining = qty_needed

        for bin_inv in available_bins:
            if qty_remaining <= 0: break
            
            available = bin_inv.available_qty
            to_take = min(available, qty_remaining)
            
            if to_take <= 0: continue

            # 2. Lock the stock
            bin_inv.reserved_qty += to_take
            bin_inv.save()
            
            # 3. Add to Task
            PickItem.objects.create(task=task, sku_id=sku_id, bin=bin_inv.bin, qty_to_pick=to_take)
            
            # 4. Audit Trail
            StockMovement.objects.create(
                sku_id=sku_id, warehouse=warehouse, bin=bin_inv.bin,
                qty_change=-to_take, movement_type='RESERVE', reference_id=str(order_id)
            )
            qty_remaining -= to_take

        if qty_remaining > 0:
            raise ValidationError(f"Not enough stock for SKU ID {sku_id}. Missing {qty_remaining}")

    return task

@transaction.atomic
def scan_pick(task_id, pick_item_id, qty_scanned, user):
    """
    Picker scans an item to confirm picking.
    """
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
    
    if item.picked_qty >= item.qty_to_pick:
        raise ValueError("Item already fully picked.")

    if item.skips.filter(is_resolved=False).exists():
        raise ValueError("Item is currently skipped and cannot be picked.")

    if item.picked_qty + int(qty_scanned) > item.qty_to_pick:
        raise ValueError(f"Scanning more than required. Already picked {item.picked_qty}, need {item.qty_to_pick}.")

    if int(qty_scanned) <= 0:
        raise ValueError("Scanned quantity must be positive.")

    item.picked_qty += int(qty_scanned)
    item.save()

    task = item.task
    # Auto-start task if pending
    if task.status == "PENDING":
        task.status = "IN_PROGRESS"
        task.picker = user
        task.save()

    # Check if task is complete
    # Logic: If NO items exist where picked_qty < qty_to_pick, then it's done.
    if not task.items.filter(picked_qty__lt=F('qty_to_pick')).exists():
        task.status = "COMPLETED"
        task.completed_at = timezone.now()
        task.save()
        # Auto-create Packing Task
        PackingTask.objects.get_or_create(picking_task=task, defaults={"status": "pending"})
        
    return item

@transaction.atomic
def complete_packing(packing_task_id, packer_user):
    """
    Finalizes the order, deducts physical stock, and generates dispatch record.
    """
    pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
    pack_task.packer = packer_user
    pack_task.status = "packed"
    pack_task.save()
    
    picking_task = pack_task.picking_task
    warehouse = picking_task.warehouse
    
    # Deduct physical stock (qty) now that it's leaving
    for pitem in picking_task.items.all():
        bi = BinInventory.objects.select_for_update().get(bin=pitem.bin, sku=pitem.sku)
        bi.qty -= pitem.picked_qty
        bi.reserved_qty -= pitem.picked_qty # Remove reservation lock
        bi.save()
        
        # Signal for Analytics/Inventory Sync
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=str(pitem.sku.id),
            warehouse_id=str(warehouse.id),
            delta_available=0, # Available was already reduced during reserve
            delta_reserved=-pitem.picked_qty,
            reference=str(picking_task.order_id),
            change_type='sale_dispatch'
        )

        StockMovement.objects.create(
            sku=pitem.sku, warehouse=warehouse, bin=pitem.bin,
            movement_type="OUTWARD", qty_change=-pitem.picked_qty, reference_id=str(picking_task.order_id)
        )

    pickup_otp = "".join(str(random.randint(0, 9)) for _ in range(4))
    dispatch = DispatchRecord.objects.create(
        packing_task=pack_task, warehouse=warehouse, order_id=picking_task.order_id,
        status="ready", pickup_otp=pickup_otp
    )
    
    dispatch_ready_for_delivery.send(sender=DispatchRecord, order_id=str(picking_task.order_id), warehouse_id=warehouse.id)
    return dispatch

# =========================================================
# EXCEPTION HANDLING (SKIPS & CANCELS)
# =========================================================

@transaction.atomic
def mark_pickitem_skipped(task_id, pick_item_id, user, reason: str, reopen_for_picker=False):
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task__id=task_id)
    if item.picked_qty >= item.qty_to_pick: raise ValueError("This item is already fully picked.")
    if item.skips.filter(is_resolved=False).exists(): raise ValueError("Item is already skipped.")

    return PickSkip.objects.create(
        task=item.task, pick_item=item, skipped_by=user,
        reason=reason, reopen_after_scan=reopen_for_picker
    )

@transaction.atomic
def resolve_skip_as_shortpick(skip: PickSkip, resolved_by_user, note: str):
    """
    Manager confirms stock is missing. Releases reservation so system knows it's gone.
    """
    if skip.is_resolved: raise ValueError("Skip already resolved.")
    item = skip.pick_item
    qty_needed = item.qty_to_pick - item.picked_qty
    
    if qty_needed <= 0:
        skip.is_resolved = True
        skip.save()
        raise ValueError("No quantity pending.")
        
    spi = ShortPickIncident.objects.create(
        skip=skip, resolved_by=resolved_by_user,
        short_picked_qty=qty_needed, notes=note
    )

    # Unlock the reserved stock because we can't find it
    bi = BinInventory.objects.get(bin=item.bin, sku=item.sku)
    bi.reserved_qty -= qty_needed
    bi.save()
    
    inventory_change_required.send(
        sender=Warehouse, sku_id=str(item.sku.id), warehouse_id=str(item.task.warehouse.id),
        delta_available=qty_needed, delta_reserved=-qty_needed, # Technically available increased (unlocked), but physically missing
        reference=str(item.task.order_id), change_type='short_pick_rollback'
    )
   
    skip.is_resolved = True
    skip.save()
    
    StockMovement.objects.create(
        sku=item.sku, warehouse=item.task.warehouse, bin=item.bin,
        movement_type="ROLLBACK", qty_change=qty_needed, reference_id=str(item.task.order_id)
    )
    return spi

@transaction.atomic
def admin_fulfillment_cancel(pick_item: PickItem, cancelled_by_user, reason: str):
    """
    Cancels specific items from an order during picking (e.g., customer request or damage).
    """
    if pick_item.qty_to_pick == pick_item.picked_qty: raise ValueError("Cannot cancel fully picked item.")
    qty_to_cancel = pick_item.qty_to_pick - pick_item.picked_qty
    
    fc_record = FulfillmentCancel.objects.create(
        pick_item=pick_item, cancelled_by=cancelled_by_user,
        reason=reason, refund_initiated=True 
    )
    
    # Release Reservation
    bi = BinInventory.objects.get(bin=pick_item.bin, sku=pick_item.sku)
    bi.reserved_qty -= qty_to_cancel
    bi.save()
    
    inventory_change_required.send(
        sender=Warehouse, sku_id=str(pick_item.sku.id), warehouse_id=str(pick_item.task.warehouse.id),
        delta_available=qty_to_cancel, delta_reserved=-qty_to_cancel,
        reference=str(pick_item.task.order_id), change_type='fulfillment_cancel_rollback'
    )

    # Update Pick Item
    pick_item.qty_to_pick = pick_item.picked_qty
    pick_item.save()

    item_fulfillment_cancelled.send(
        sender=FulfillmentCancel,
        order_id=str(pick_item.task.order_id),
        sku_id=str(pick_item.sku.id),
        qty=qty_to_cancel,
        reason=reason
    )

    return fc_record

# =========================================================
# INBOUND (GRN & PUTAWAY) - RESTORED
# =========================================================

@transaction.atomic
def create_grn_and_putaway(warehouse_id, grn_number, items, created_by):
    """
    Creates GRN and generates Putaway Tasks for staff.
    items = [{'sku_id': 1, 'qty': 100}, ...]
    """
    warehouse = Warehouse.objects.get(id=warehouse_id)
    grn = GRN.objects.create(
        warehouse=warehouse, grn_number=grn_number,
        status="received", created_by=created_by
    )
    
    grn_items = []
    for item in items:
        grn_items.append(GRNItem(
            grn=grn, 
            sku_id=item['sku_id'], 
            expected_qty=item['qty'], 
            received_qty=item['qty'] # Assuming full receipt for now
        ))
    GRNItem.objects.bulk_create(grn_items)
    
    # Create Putaway Task
    putaway_task = PutawayTask.objects.create(grn=grn, warehouse=warehouse, status="pending")
    
    # Create Putaway Items (Work instructions)
    putaway_items = []
    # Need to fetch IDs after bulk_create
    saved_grn_items = GRNItem.objects.filter(grn=grn)
    
    for g_item in saved_grn_items:
        putaway_items.append(PutawayItem(task=putaway_task, grn_item=g_item))
        
    PutawayItem.objects.bulk_create(putaway_items)
    
    return grn, putaway_task

@transaction.atomic
def place_putaway_item(task_id, putaway_item_id, bin_id, qty_placed, user):
    """
    Staff places item into a Bin.
    """
    item = PutawayItem.objects.select_for_update().get(id=putaway_item_id, task__id=task_id)
    grn_item = item.grn_item
    
    if item.placed_qty + int(qty_placed) > grn_item.received_qty:
        raise ValueError("Cannot place more than received quantity.")

    bin_obj = Bin.objects.get(id=bin_id)
    warehouse = item.task.warehouse
    sku = grn_item.sku
    
    # Update Physical Inventory
    bi, created = BinInventory.objects.get_or_create(bin=bin_obj, sku=sku, defaults={'qty': 0})
    bi.qty += int(qty_placed)
    bi.save()

    # Send Signal (Available stock increased)
    inventory_change_required.send(
        sender=Warehouse, sku_id=str(sku.id), warehouse_id=str(warehouse.id),
        delta_available=int(qty_placed), delta_reserved=0,
        reference=grn_item.grn.grn_number, change_type='putaway'
    )
    
    # Update Task Progress
    item.placed_qty += int(qty_placed)
    item.placed_bin = bin_obj
    item.save()
    
    # Check if Task Complete
    total_received = item.task.grn.items.aggregate(total=Sum('received_qty'))['total'] or 0
    total_placed = item.task.items.aggregate(total=Sum('placed_qty'))['total'] or 0
    
    if total_placed >= total_received:
        item.task.status = 'completed'
        item.task.save()
        item.task.grn.status = 'putaway_complete'
        item.task.grn.save()
    
    StockMovement.objects.create(
        sku=sku, warehouse=warehouse, bin=bin_obj,
        movement_type="PUTAWAY", qty_change=int(qty_placed), reference_id=grn_item.grn.grn_number
    )
    return item

# =========================================================
# CYCLE COUNT (AUDIT) - RESTORED
# =========================================================

@transaction.atomic
def create_cycle_count(warehouse_id, user, sample_bins=None):
    """
    Generates a Cycle Count task for specific bins or random ones.
    """
    warehouse = Warehouse.objects.get(id=warehouse_id)
    cc_task = CycleCountTask.objects.create(warehouse=warehouse, task_user=user, status='pending')
    
    if sample_bins:
        bins = Bin.objects.filter(id__in=sample_bins)
    else:
        # Logic: Pick 20 random bins that have stock
        bins = Bin.objects.filter(inventory__qty__gt=0, zone__warehouse=warehouse).distinct()[:20] 

    cc_items = []
    for bin_obj in bins:
        for bi in BinInventory.objects.filter(bin=bin_obj, qty__gt=0):
            cc_items.append(CycleCountItem(
                task=cc_task, 
                bin=bin_obj, 
                sku=bi.sku, 
                expected_qty=bi.qty # Snapshot of what system thinks
            ))
    CycleCountItem.objects.bulk_create(cc_items)
    return cc_task

@transaction.atomic
def record_cycle_count_item(task_id, bin_id, sku_id, counted_qty, user):
    """
    Records result of counting. Adjusts inventory if mismatch found.
    """
    cc_item = CycleCountItem.objects.select_for_update().get(task_id=task_id, bin_id=bin_id, sku_id=sku_id)
    
    if cc_item.counted_qty is not None: 
        raise ValueError("This item has already been counted.")
        
    cc_item.counted_qty = int(counted_qty)
    delta = cc_item.counted_qty - cc_item.expected_qty
    cc_item.adjusted = (delta != 0)
    
    if delta != 0:
        # Mismatch found! Adjust inventory immediately.
        bi = BinInventory.objects.get(bin_id=bin_id, sku_id=sku_id)
        bi.qty += delta
        # Prevent negative stock if something went really wrong
        if bi.qty < 0: bi.qty = 0 
        bi.save()
        
        inventory_change_required.send(
            sender=Warehouse, sku_id=str(sku_id), warehouse_id=str(cc_item.task.warehouse.id),
            delta_available=delta, delta_reserved=0,
            reference=str(cc_item.task.id), change_type='cycle_count_adjustment'
        )
        
        StockMovement.objects.create(
            sku_id=sku_id, warehouse=cc_item.task.warehouse, bin_id=bin_id,
            movement_type="CYCLE_COUNT", qty_change=delta, reference_id=str(cc_item.task.id)
        )
        
    cc_item.save()
    
    # Check completion
    if not cc_item.task.items.filter(counted_qty__isnull=True).exists():
        cc_item.task.status = 'completed'
        cc_item.task.save()

    return cc_item

# =========================================================
# UTILS
# =========================================================

def assign_task_to_picker(picking_task):
    """
    Round-Robin Assignment logic.
    """
    available_pickers = EmployeeProfile.objects.filter(
        role='PICKER',
        is_active_employee=True,
        warehouse_code=picking_task.warehouse.code
    ).order_by('last_task_assigned_at')

    picker_profile = available_pickers.first()
    
    if picker_profile:
        picking_task.picker = picker_profile.user
        picking_task.status = 'PENDING'
        picking_task.save()
        
        picker_profile.last_task_assigned_at = timezone.now()
        picker_profile.save()
        return True, f"Assigned to {picker_profile.user.full_name}"
    
    return False, "No available pickers found."