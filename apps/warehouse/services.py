# apps/warehouse/services.py
import logging
import random
from django.db import transaction, models
from django.db.models import Sum, F, Case, When, Value
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Warehouse, Bin, BinInventory, StockMovement, PickingTask, PickItem,
    PackingTask, DispatchRecord, PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, GRNItem, PutawayTask, PutawayItem, CycleCountTask, CycleCountItem
)
from .signals import (
    inventory_change_required,
    dispatch_ready_for_delivery,
    item_fulfillment_cancelled,
)
from .exceptions import OutOfStockError
from .notifications import notify_packer_new_task, notify_dispatch_ready

logger = logging.getLogger(__name__)

# =========================================================
# OUTBOUND (ORDER → RESERVATION → PICK → PACK → DISPATCH)
# =========================================================

@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items_needed):
    """
    Allocates stock from bins.
    PRO FIX: Uses 'skip_locked=True' to allow concurrent pickers to grab different bins 
    for the same SKU without blocking.
    """
    warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)
    
    task = PickingTask.objects.create(
        order_id=str(order_id),
        warehouse=warehouse,
        status=PickingTask.TaskStatus.PENDING,
    )

    # Sort to prevent deadlocks (canonical ordering)
    items_needed = sorted(items_needed, key=lambda x: str(x['sku_id']))

    for item in items_needed:
        sku_id = item["sku_id"]
        qty_needed = int(item["qty"])
        qty_remaining = qty_needed

        # OPTIMIZED LOCKING STRATEGY:
        # 1. Filter bins with actual available stock (qty > reserved)
        # 2. Order by 'qty' ASC (clears small fragmented bins first) OR DESC (efficiency)
        # 3. select_for_update(skip_locked=True) allows other txns to skip these locked rows
        bin_qs = (
            BinInventory.objects
            .select_for_update(skip_locked=True)
            .select_related("bin__zone__warehouse")
            .filter(
                bin__zone__warehouse=warehouse,
                sku_id=sku_id,
                qty__gt=F("reserved_qty"),
            )
            .order_by("qty") # Strategy: Empty small bins first
        )

        for bin_inv in bin_qs:
            if qty_remaining <= 0:
                break

            available = bin_inv.available_qty
            if available <= 0:
                continue

            to_reserve = min(available, qty_remaining)
            
            bin_inv.reserved_qty += to_reserve
            bin_inv.save(update_fields=['reserved_qty'])

            PickItem.objects.create(
                task=task,
                sku_id=sku_id,
                bin=bin_inv.bin,
                qty_to_pick=to_reserve,
            )

            # Signal Logical Inventory Update (async via receiver)
            inventory_change_required.send(
                sender=Warehouse,
                sku_id=str(sku_id),
                warehouse_id=str(warehouse.id),
                delta_available=-to_reserve,
                delta_reserved=to_reserve,
                reference=str(order_id),
                change_type="order_reservation",
            )

            qty_remaining -= to_reserve

        if qty_remaining > 0:
            logger.error(f"Stock Mismatch! SKU {sku_id} in WH {warehouse_id}. Needed {qty_needed}, Short {qty_remaining}")
            raise OutOfStockError(f"Insufficient stock for SKU {sku_id}. Short by {qty_remaining}")

    PackingTask.objects.create(
        picking_task=task,
        status=PackingTask.PackStatus.PENDING,
    )
    
    return task


@transaction.atomic
def scan_pick(task_id, pick_item_id, qty_scanned, user):
    item = PickItem.objects.select_for_update().select_related("task").get(
        id=pick_item_id,
        task_id=task_id,
    )

    if item.picked_qty >= item.qty_to_pick:
        raise ValidationError("Item already fully picked.")

    if item.skips.filter(is_resolved=False).exists():
        raise ValidationError("Item is marked as skipped.")

    qty_scanned = int(qty_scanned)
    if qty_scanned <= 0:
        raise ValidationError("Quantity must be positive.")

    if item.picked_qty + qty_scanned > item.qty_to_pick:
        raise ValidationError(f"Over-picking detected. Max allowed: {item.qty_to_pick - item.picked_qty}")

    item.picked_qty += qty_scanned
    item.save(update_fields=['picked_qty'])

    task = item.task
    if task.status == PickingTask.TaskStatus.PENDING:
        task.status = PickingTask.TaskStatus.IN_PROGRESS
        task.picker = user
        task.save(update_fields=['status', 'picker'])

    pending_items = task.items.filter(picked_qty__lt=F("qty_to_pick")).exists()
    
    if not pending_items:
        task.status = PickingTask.TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
        
        # Check if PackingTask exists before accessing (defensive)
        if hasattr(task, 'packing_task'):
            notify_packer_new_task(task.packing_task)

    return item


@transaction.atomic
def complete_packing(packing_task_id, packer_user):
    pack_task = PackingTask.objects.select_for_update().select_related(
        "picking_task__warehouse"
    ).get(id=packing_task_id)

    if pack_task.status == PackingTask.PackStatus.PACKED:
        raise ValidationError("Task already packed.")

    picking_task = pack_task.picking_task
    warehouse = picking_task.warehouse

    items = picking_task.items.select_related("bin", "sku").all()
    
    for pitem in items:
        # Lock specific bin-sku row
        bi = BinInventory.objects.select_for_update().get(
            bin=pitem.bin,
            sku=pitem.sku,
        )
        
        if bi.qty < pitem.picked_qty:
            logger.critical(f"Data Integrity Error: Bin {bi.bin.bin_code} insufficient qty.")
            raise ValidationError(f"Integrity Error: Bin {bi.bin.bin_code} mismatch.")
        
        # Atomic Updates: Reduce physical qty, reduce reserved
        bi.qty = F('qty') - pitem.picked_qty
        
        # Conditional update to prevent negative reserved
        bi.reserved_qty = Case(
            When(reserved_qty__gte=pitem.picked_qty, then=F('reserved_qty') - pitem.picked_qty),
            default=Value(0),
            output_field=models.IntegerField()
        )
        bi.save()

        # Signal for logical inventory sync (Release reserved)
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=str(pitem.sku.id),
            warehouse_id=str(warehouse.id),
            delta_available=0,
            delta_reserved=-pitem.picked_qty, # Release the hold
            reference=str(picking_task.order_id),
            change_type="sale_dispatch",
        )

        StockMovement.objects.create(
            sku=pitem.sku,
            warehouse=warehouse,
            bin=pitem.bin,
            movement_type=StockMovement.MovementType.OUTWARD,
            qty_change=-pitem.picked_qty,
            reference_id=str(picking_task.order_id),
            performed_by=packer_user,
        )

    pack_task.packer = packer_user
    pack_task.status = PackingTask.PackStatus.PACKED
    pack_task.save(update_fields=['packer', 'status'])

    pickup_otp = "".join(str(random.randint(0, 9)) for _ in range(4))
    
    # Ensure OneToOne relation doesn't crash if record exists (idempotency)
    dispatch, created = DispatchRecord.objects.get_or_create(
        packing_task=pack_task,
        defaults={
            'warehouse': warehouse,
            'order_id': picking_task.order_id,
            'status': DispatchRecord.DispatchStatus.READY,
            'pickup_otp': pickup_otp
        }
    )

    if created:
        transaction.on_commit(lambda: dispatch_ready_for_delivery.send(
            sender=DispatchRecord,
            dispatch_id=dispatch.id,
            order_id=str(picking_task.order_id),
            warehouse_id=warehouse.id,
            pickup_otp=pickup_otp,
        ))
        notify_dispatch_ready(dispatch)
    
    return dispatch

@transaction.atomic
def verify_dispatch_otp(dispatch_id, otp, user=None):
    dispatch = DispatchRecord.objects.select_for_update().get(id=dispatch_id)

    if dispatch.status == DispatchRecord.DispatchStatus.HANDED_OVER:
        raise ValidationError("Order already handed over.")

    if not dispatch.pickup_otp:
        raise ValidationError("OTP not generated for this dispatch.")

    if str(dispatch.pickup_otp) != str(otp):
        raise ValidationError("Invalid OTP.")

    dispatch.status = DispatchRecord.DispatchStatus.HANDED_OVER
    dispatch.save(update_fields=["status"])
    return dispatch

# --- Other services (skips/GRN/CycleCount) assumed similar, included here for completeness of file ---
# (Keeping original implementations for brevity unless specific bugs were found, 
# but ensuring imports and transaction decorators are present)

@transaction.atomic
def mark_pickitem_skipped(task_id, pick_item_id, user, reason: str, reopen_for_picker=False):
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task__id=task_id)
    if item.picked_qty >= item.qty_to_pick:
        raise ValueError("This item is already fully picked.")
    if item.skips.filter(is_resolved=False).exists():
        raise ValueError("Item is already skipped.")

    return PickSkip.objects.create(
        task=item.task,
        pick_item=item,
        skipped_by=user,
        reason=reason,
        reopen_after_scan=reopen_for_picker,
    )

@transaction.atomic
def resolve_skip_as_shortpick(skip: PickSkip, resolved_by_user, note: str):
    if skip.is_resolved:
        raise ValueError("Skip already resolved.")

    item = skip.pick_item
    qty_needed = item.qty_to_pick - item.picked_qty
    if qty_needed <= 0:
        skip.is_resolved = True
        skip.save()
        raise ValueError("No quantity pending.")

    spi = ShortPickIncident.objects.create(
        skip=skip,
        resolved_by=resolved_by_user,
        short_picked_qty=qty_needed,
        notes=note,
    )

    # Release Physical Reservation
    bi = BinInventory.objects.get(bin=item.bin, sku=item.sku)
    bi.reserved_qty = max(0, bi.reserved_qty - qty_needed)
    bi.save()

    # Logical Unlock
    inventory_change_required.send(
        sender=Warehouse,
        sku_id=str(item.sku.id),
        warehouse_id=str(item.task.warehouse.id),
        delta_available=qty_needed,
        delta_reserved=-qty_needed,
        reference=str(item.task.order_id),
        change_type="short_pick_rollback",
    )

    skip.is_resolved = True
    skip.save()

    StockMovement.objects.create(
        sku=item.sku,
        warehouse=item.task.warehouse,
        bin=item.bin,
        movement_type=StockMovement.MovementType.ROLLBACK,
        qty_change=qty_needed,
        reference_id=str(item.task.order_id),
        performed_by=resolved_by_user,
    )
    return spi

@transaction.atomic
def admin_fulfillment_cancel(pick_item: PickItem, cancelled_by_user, reason: str):
    if pick_item.qty_to_pick == pick_item.picked_qty:
        raise ValueError("Cannot cancel fully picked item.")

    qty_to_cancel = pick_item.qty_to_pick - pick_item.picked_qty

    fc_record = FulfillmentCancel.objects.create(
        pick_item=pick_item,
        cancelled_by=cancelled_by_user,
        reason=reason,
        refund_initiated=True,
    )

    bi = BinInventory.objects.get(bin=pick_item.bin, sku=pick_item.sku)
    bi.reserved_qty = max(0, bi.reserved_qty - qty_to_cancel)
    bi.save()

    inventory_change_required.send(
        sender=Warehouse,
        sku_id=str(pick_item.sku.id),
        warehouse_id=str(pick_item.task.warehouse.id),
        delta_available=qty_to_cancel,
        delta_reserved=-qty_to_cancel,
        reference=str(pick_item.task.order_id),
        change_type="fulfillment_cancel_rollback",
    )

    pick_item.qty_to_pick = pick_item.picked_qty
    pick_item.save()

    item_fulfillment_cancelled.send(
        sender=FulfillmentCancel,
        order_id=str(pick_item.task.order_id),
        sku_id=str(pick_item.sku.id),
        qty=qty_to_cancel,
        reason=reason,
    )

    return fc_record

@transaction.atomic
def create_grn_and_putaway(warehouse_id, grn_number, items, created_by):
    warehouse = Warehouse.objects.get(id=warehouse_id)
    grn = GRN.objects.create(
        warehouse=warehouse,
        grn_number=grn_number,
        status=GRN.GrnStatus.RECEIVED,
        created_by=created_by,
    )

    grn_items = [
        GRNItem(
            grn=grn,
            sku_id=item["sku_id"],
            expected_qty=item["qty"],
            received_qty=item["qty"],
        )
        for item in items
    ]
    GRNItem.objects.bulk_create(grn_items)

    putaway_task = PutawayTask.objects.create(
        grn=grn,
        warehouse=warehouse,
        status=PutawayTask.PutawayStatus.PENDING,
    )

    saved_grn_items = GRNItem.objects.filter(grn=grn)
    putaway_items = [PutawayItem(task=putaway_task, grn_item=g) for g in saved_grn_items]
    PutawayItem.objects.bulk_create(putaway_items)

    return grn, putaway_task

@transaction.atomic
def place_putaway_item(task_id, putaway_item_id, bin_id, qty_placed, user):
    item = PutawayItem.objects.select_for_update().select_related("task__warehouse", "grn_item__sku", "grn_item__grn").get(id=putaway_item_id, task__id=task_id)
    grn_item = item.grn_item

    qty_placed = int(qty_placed)
    if item.placed_qty + qty_placed > grn_item.received_qty:
        raise ValueError("Cannot place more than received quantity.")

    bin_obj = Bin.objects.get(id=bin_id)
    warehouse = item.task.warehouse
    sku = grn_item.sku

    bi, _ = BinInventory.objects.get_or_create(bin=bin_obj, sku=sku, defaults={"qty": 0})
    bi.qty += qty_placed
    bi.save()

    inventory_change_required.send(
        sender=Warehouse,
        sku_id=str(sku.id),
        warehouse_id=str(warehouse.id),
        delta_available=qty_placed,
        delta_reserved=0,
        reference=grn_item.grn.grn_number,
        change_type="putaway",
    )

    item.placed_qty += qty_placed
    item.placed_bin = bin_obj
    item.save()

    total_received = item.task.grn.items.aggregate(total=Sum("received_qty"))["total"] or 0
    total_placed = item.task.items.aggregate(total=Sum("placed_qty"))["total"] or 0

    if total_placed >= total_received:
        item.task.status = PutawayTask.PutawayStatus.COMPLETED
        item.task.save()
        item.task.grn.status = GRN.GrnStatus.PUTAWAY_COMPLETE
        item.task.grn.save()

    StockMovement.objects.create(
        sku=sku,
        warehouse=warehouse,
        bin=bin_obj,
        movement_type=StockMovement.MovementType.PUTAWAY,
        qty_change=qty_placed,
        reference_id=grn_item.grn.grn_number,
        performed_by=user,
    )
    return item

@transaction.atomic
def create_cycle_count(warehouse_id, user, sample_bins=None):
    warehouse = Warehouse.objects.get(id=warehouse_id)
    cc_task = CycleCountTask.objects.create(
        warehouse=warehouse,
        task_user=user,
        status=CycleCountTask.CcStatus.PENDING,
    )

    if sample_bins:
        bins = Bin.objects.filter(id__in=sample_bins)
    else:
        # Random sample
        bins = Bin.objects.filter(inventory__qty__gt=0, zone__warehouse=warehouse).distinct().order_by("?")[:20]

    cc_items = []
    for b in bins:
        for bi in BinInventory.objects.filter(bin=b, qty__gt=0):
            cc_items.append(CycleCountItem(task=cc_task, bin=b, sku=bi.sku, expected_qty=bi.qty))
    
    CycleCountItem.objects.bulk_create(cc_items)
    return cc_task

@transaction.atomic
def record_cycle_count_item(task_id, bin_id, sku_id, counted_qty, user):
    cc_item = CycleCountItem.objects.select_for_update().select_related("task__warehouse").get(task_id=task_id, bin_id=bin_id, sku_id=sku_id)

    if cc_item.counted_qty is not None:
        raise ValueError("This item has already been counted.")

    cc_item.counted_qty = int(counted_qty)
    delta = cc_item.counted_qty - cc_item.expected_qty
    cc_item.adjusted = delta != 0

    if delta != 0:
        bi = BinInventory.objects.get(bin_id=bin_id, sku_id=sku_id)
        # Ensure we don't go negative on a logic error, though CC is absolute truth
        new_qty = bi.qty + delta
        if new_qty < 0: 
             new_qty = 0 # Cannot have negative stock
             delta = -bi.qty # Adjust delta to actual removal
        
        bi.qty = new_qty
        bi.save()

        inventory_change_required.send(
            sender=Warehouse,
            sku_id=str(sku_id),
            warehouse_id=str(cc_item.task.warehouse.id),
            delta_available=delta,
            delta_reserved=0,
            reference=str(cc_item.task.id),
            change_type="cycle_count_adjustment",
        )

        StockMovement.objects.create(
            sku_id=sku_id,
            warehouse=cc_item.task.warehouse,
            bin_id=bin_id,
            movement_type=StockMovement.MovementType.CYCLE_COUNT,
            qty_change=delta,
            reference_id=str(cc_item.task.id),
            performed_by=user,
        )

    cc_item.save()
    return cc_item