# apps/warehouse/services.py
import random
from django.db import transaction, models
from django.utils import timezone
from .models import (
    Warehouse, Bin, BinInventory, StockMovement, 
    PickingTask, PickItem, PackingTask, DispatchRecord,
    PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, GRNItem, PutawayTask, PutawayItem, CycleCountItem
)
from apps.inventory.models import InventoryStock # <-- READ-ONLY CHECK KE LIYE ZAROORI HAI
from .exceptions import OutOfStockError, ReservationFailedError
from .signals import dispatch_ready_for_delivery, inventory_change_required # <-- NAYA SIGNAL IMPORT KIYA
from apps.orders.models import Order # Refund ke liye zaroori
from apps.payments.tasks import process_order_refund_task # <-- Naya Import for Decoupling
from .notifications import notify_packer_new_task 
from django.db.models import Sum


@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items):
    """
    Order aane par stock reserve karta hai. InventoryStock update ko signal se badla.
    """
    allocations = {}
    warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

    for it in items:
        sku_id = it["sku_id"]
        qty_needed = int(it["qty"])

        # 1. Check Aggregate Stock (READ-ONLY CHECK remains for atomicity)
        try:
            inv = InventoryStock.objects.select_for_update().get(warehouse=warehouse, sku_id=sku_id)
        except InventoryStock.DoesNotExist:
            raise OutOfStockError(f"SKU {sku_id} not found in warehouse.")
            
        if inv.available_qty < qty_needed:
            raise OutOfStockError(f"Not enough stock for SKU {sku_id}. Need {qty_needed}, Have {inv.available_qty}")

        # 2. Reserve from Bins (WMS Internal Model - remains)
        bin_qs = BinInventory.objects.select_for_update().filter(
            bin__shelf__aisle__zone__warehouse=warehouse, 
            sku_id=sku_id
        ).order_by("-qty")

        allocations[sku_id] = []
        remaining = qty_needed

        for bi in bin_qs:
            if remaining <= 0: break
            
            # Kitna le sakte hain is bin se?
            available_in_bin = bi.qty - bi.reserved_qty
            take = min(remaining, available_in_bin)
            
            if take <= 0: continue

            bi.reserved_qty += take
            bi.save()
            
            allocations[sku_id].append({"bin_id": bi.bin_id, "qty": take})
            
            # Audit log
            StockMovement.objects.create(
                sku_id=sku_id, warehouse=warehouse, bin=bi.bin,
                change_type="reserve", delta_qty=-take, reference_id=str(order_id)
            )
            
            remaining -= take

        if remaining > 0:
            raise ReservationFailedError(f"Bin integrity error for SKU {sku_id}. Aggregate says yes, Bins say no.")

        # 3. Update Aggregate - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            delta_available=-qty_needed,
            delta_reserved=qty_needed,
            reference=str(order_id),
            change_type='reserve'
        )

    return allocations

@transaction.atomic
def create_picking_task_from_reservation(order_id, warehouse_id, allocations):
    task = PickingTask.objects.create(
        order_id=str(order_id),
        warehouse_id=warehouse_id,
        status="pending"
    )
    
    for sku_id, alloc_list in allocations.items():
        for alloc in alloc_list:
            PickItem.objects.create(
                task=task,
                sku_id=sku_id,
                bin_id=alloc["bin_id"],
                qty=alloc["qty"]
            )
    return task

@transaction.atomic
def scan_pick(task_id, pick_item_id, qty_scanned, user):
    """
    Picker item scan karta hai.
    """
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
    
    # FIX: Agar item skip ho chuka hai, toh reject karein
    if item.skips.filter(is_resolved=False).exists():
        raise ValueError("Item is currently skipped and cannot be picked.")

    if item.picked_qty + int(qty_scanned) > item.qty:
        raise ValueError("Scanning more than required!")

    item.picked_qty += int(qty_scanned)
    item.save()

    task = item.task
    if task.status == "pending":
        task.status = "in_progress"
        task.started_at = timezone.now()
        task.picker = user # Assign picker
        task.save()

    # Check if task is complete
    if not task.items.filter(picked_qty__lt=models.F('qty')).exists():
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()
        
        # Auto-create packing task
        packing_task, _ = PackingTask.objects.get_or_create(picking_task=task, defaults={"status": "pending"})
        
        # Notify Packer
        notify_packer_new_task(packing_task) # <-- Notification add kiya
        
    return item

@transaction.atomic
def complete_packing(packing_task_id, packer_user):
    pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
    pack_task.packer = packer_user
    pack_task.status = "packed"
    pack_task.save()
    
    picking_task = pack_task.picking_task
    warehouse = picking_task.warehouse
    
    # 1. Inventory Deduct Karo (Permanently Remove)
    for pitem in picking_task.items.all():
        # Bin Inventory Update (WMS Internal Model - remains)
        bi = BinInventory.objects.get(bin=pitem.bin, sku=pitem.sku)
        bi.qty -= pitem.qty
        bi.reserved_qty -= pitem.qty # Reservation free kar do
        bi.save()
        
        # Aggregate Inventory Update - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=pitem.sku_id,
            warehouse_id=warehouse.id,
            delta_available=0, # Available stock par koi asar nahi, sirf reserved stock ghatega
            delta_reserved=-pitem.qty, # Reserved stock ghatao
            reference=str(picking_task.order_id),
            change_type='sale_dispatch'
        )
        
        # Log remains (WMS internal)
        StockMovement.objects.create(
            sku=pitem.sku, warehouse=warehouse, bin=pitem.bin,
            change_type="sale_dispatch", delta_qty=-pitem.qty, reference_id=str(picking_task.order_id)
        )

    # 2. Dispatch Record Create Karo
    pickup_otp = "".join(str(random.randint(0, 9)) for _ in range(4))
    dispatch = DispatchRecord.objects.create(
        packing_task=pack_task,
        warehouse=warehouse,
        order_id=picking_task.order_id,
        status="ready",
        pickup_otp=pickup_otp
    )
    
    # 3. Signal Bhejo (Delivery App ke liye)
    dispatch_ready_for_delivery.send(
        sender=DispatchRecord,
        dispatch_id=dispatch.id,
        order_id=dispatch.order_id,
        warehouse_id=warehouse.id,
        pickup_otp=pickup_otp
    )
    
    return dispatch

# --- New Services for Picking Error Resolution ---

@transaction.atomic
def mark_pickitem_skipped(task_id, pick_item_id, user, reason: str, reopen_for_picker=False):
    """
    Picker item ko skip mark karta hai.
    """
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task__id=task_id)
    
    if item.picked_qty >= item.qty:
        raise ValueError("This item is already fully picked.")

    if item.skips.filter(is_resolved=False).exists():
        raise ValueError("Item is already skipped and awaiting resolution.")

    skip = PickSkip.objects.create(
        task=item.task,
        pick_item=item,
        skipped_by=user,
        reason=reason,
        reopen_after_scan=reopen_for_picker
    )
    # TODO: Real-time broadcast to supervisor dashboard
    return skip

@transaction.atomic
def resolve_skip_as_shortpick(skip: PickSkip, resolved_by_user, note: str):
    """
    Short Pick declare karta hai aur inventory adjust karta hai.
    InventoryStock update ko signal se badla.
    """
    if skip.is_resolved:
        raise ValueError("Skip already resolved.")
        
    item = skip.pick_item
    qty_needed = item.qty - item.picked_qty
    
    if qty_needed <= 0:
        skip.is_resolved = True
        skip.save(update_fields=['is_resolved'])
        raise ValueError("No quantity pending for this item.")
        
    # ShortPick record banayein
    spi = ShortPickIncident.objects.create(
        skip=skip,
        resolved_by=resolved_by_user,
        short_picked_qty=qty_needed,
        notes=note
    )

    # BinInventory se reservation hatao (agar item reserved tha) - (WMS Internal Model - remains)
    bi = BinInventory.objects.get(bin=item.bin, sku=item.sku)
    bi.reserved_qty -= qty_needed
    bi.save(update_fields=['reserved_qty'])
    
    # InventoryStock se reservation hatao aur available stock mein wapas dalo - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
    inventory_change_required.send(
        sender=Warehouse,
        sku_id=item.sku_id,
        warehouse_id=item.task.warehouse.id,
        delta_available=qty_needed, # Available stock mein wapas
        delta_reserved=-qty_needed, # Reservation hatao
        reference=str(item.task.order_id),
        change_type='short_pick_rollback'
    )

    # Skip ko resolve mark karein
    skip.is_resolved = True
    skip.save(update_fields=['is_resolved'])
    
    # StockMovement log (remains)
    StockMovement.objects.create(
        sku=item.sku, warehouse=item.task.warehouse, bin=item.bin,
        change_type="short_pick_rollback", delta_qty=qty_needed, reference_id=str(item.task.order_id)
    )
    
    return spi

@transaction.atomic
def admin_fulfillment_cancel(pick_item: PickItem, cancelled_by_user, reason: str):
    """
    Item ko order se permanently cancel karta hai (Refund ke saath).
    InventoryStock update ko signal se badla. Refund service call ko task se badla.
    """
    if pick_item.qty == pick_item.picked_qty:
        raise ValueError("Cannot cancel item that is already fully picked.")
    
    qty_to_cancel = pick_item.qty - pick_item.picked_qty
    
    # 1. FC Record
    fc_record = FulfillmentCancel.objects.create(
        pick_item=pick_item,
        cancelled_by=cancelled_by_user,
        reason=reason,
        refund_initiated=False # Abhi sirf record banaya
    )
    
    # 2. Inventory Rollback/Adjustment
    
    # BinInventory se pending reservation remove karein (WMS internal model - remains)
    bi = BinInventory.objects.get(bin=pick_item.bin, sku=pick_item.sku)
    bi.reserved_qty -= qty_to_cancel
    bi.save(update_fields=['reserved_qty'])
    
    # InventoryStock se reservation hatao aur available stock mein wapas dalo - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
    inventory_change_required.send(
        sender=Warehouse,
        sku_id=pick_item.sku_id,
        warehouse_id=pick_item.task.warehouse.id,
        delta_available=qty_to_cancel, # Available stock mein wapas
        delta_reserved=-qty_to_cancel, # Reservation hatao
        reference=str(pick_item.task.order_id),
        change_type='fulfillment_cancel_rollback'
    )

    # PickItem ko forcefully picked mark karein (remains)
    pick_item.qty = pick_item.picked_qty # PickItem ki required qty ko picked qty ke barabar kar do.
    pick_item.save(update_fields=['qty'])

    # 3. Refund Initiate Karo
    order = Order.objects.get(id=pick_item.task.order_id)
    
    # OrderItem se unit price nikal kar refund amount calculate karein
    order_item = order.items.filter(sku=pick_item.sku).first()
    if not order_item: raise Exception("Order Item not found for FC.")
    
    refund_amount = order_item.unit_price * qty_to_cancel
    
    if order.payment_status == 'paid':
        # Direct call ki jagah Celery Task ko call karein
        process_order_refund_task.delay(
            order_id=str(order.id), 
            amount=float(refund_amount), 
            reason=f"FC: {reason}"
        )
        fc_record.refund_initiated = True
        fc_record.save(update_fields=['refund_initiated'])
    
    # OrderTimeline mein entry (optional)
    # ...

    return fc_record

# --- New Services for GRN/Putaway & Cycle Count ---

@transaction.atomic
def create_grn_and_putaway(warehouse_id, grn_number, items, created_by):
    """
    GRN (Inbound) record banata hai aur Putaway Task generate karta hai.
    items = [{"sku_id": <uuid>, "qty": int}, ...]
    """
    warehouse = Warehouse.objects.get(id=warehouse_id)
    
    # 1. GRN Record
    grn = GRN.objects.create(
        warehouse=warehouse,
        grn_number=grn_number,
        status="received", # Assume received at entry point
        created_by=created_by
    )

    # 2. GRN Items
    grn_items = [
        GRNItem(grn=grn, sku_id=item['sku_id'], expected_qty=item['qty'], received_qty=item['qty'])
        for item in items
    ]
    GRNItem.objects.bulk_create(grn_items)
    
    # 3. Putaway Task
    putaway_task = PutawayTask.objects.create(grn=grn, warehouse=warehouse, status="pending")
    
    # 4. Putaway Items
    putaway_items = [
        PutawayItem(task=putaway_task, grn_item=g_item)
        for g_item in grn_items
    ]
    PutawayItem.objects.bulk_create(putaway_items)
    
    return grn, putaway_task

@transaction.atomic
def place_putaway_item(task_id, putaway_item_id, bin_id, qty_placed, user):
    """
    Putaway user item ko bin mein rakhta hai (scans).
    InventoryStock update ko signal se badla.
    """
    item = PutawayItem.objects.select_for_update().get(id=putaway_item_id, task__id=task_id)
    grn_item = item.grn_item
    
    if item.placed_qty + qty_placed > grn_item.received_qty:
        raise ValueError("Cannot place more than received quantity.")

    bin_obj = Bin.objects.get(id=bin_id)
    warehouse = item.task.warehouse
    sku = grn_item.sku
    
    # 1. BinInventory update/create (WMS internal model - remains)
    bi, _ = BinInventory.objects.get_or_create(bin=bin_obj, sku=sku, defaults={'qty': 0})
    bi.qty += qty_placed
    bi.save(update_fields=['qty'])

    # 2. InventoryStock update - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
    inventory_change_required.send(
        sender=Warehouse,
        sku_id=sku.id,
        warehouse_id=warehouse.id,
        delta_available=qty_placed, # Available stock mein add
        delta_reserved=0,
        reference=grn_item.grn.grn_number,
        change_type='putaway'
    )
    
    # 3. PutawayItem record update (remains)
    item.placed_qty += qty_placed
    item.placed_bin = bin_obj
    item.save(update_fields=['placed_qty', 'placed_bin'])
    
    # 4. Task status check/update (remains)
    if item.task.items.aggregate(total_placed=Sum('placed_qty'))['total_placed'] == grn_item.grn.items.aggregate(total_received=Sum('received_qty'))['total_received']:
        item.task.status = 'completed'
        item.task.save(update_fields=['status'])
    
    # 5. StockMovement log (remains)
    StockMovement.objects.create(
        sku=sku, warehouse=warehouse, bin=bin_obj,
        change_type="putaway", delta_qty=qty_placed, reference_id=grn_item.grn.grn_number
    )

    return item


@transaction.atomic
def create_cycle_count(warehouse_id, user, sample_bins=None):
    """
    Naya Cycle Count Task banata hai. Agar sample_bins diya hai, toh unhi bins ko include karega.
    """
    warehouse = Warehouse.objects.get(id=warehouse_id)
    
    # 1. Task create karo
    cc_task = CycleCountTask.objects.create(
        warehouse=warehouse,
        task_user=user,
        status='pending'
    )
    
    # 2. Bins/SKUs select karo
    if sample_bins:
        bins = Bin.objects.filter(id__in=sample_bins)
    else:
        # Simple Logic: Aise bins select karo jahan stock ho (for efficiency)
        bins = Bin.objects.filter(inventory__qty__gt=0, shelf__aisle__zone__warehouse=warehouse).distinct()[:20] 

    cc_items_to_create = []
    
    for bin_obj in bins:
        # Har bin mein maujood har SKU ki entry banayein
        bin_inventories = BinInventory.objects.filter(bin=bin_obj, qty__gt=0)
        
        for bi in bin_inventories:
            cc_items_to_create.append(
                CycleCountItem(
                    task=cc_task,
                    bin=bin_obj,
                    sku=bi.sku,
                    expected_qty=bi.qty # DB ka current stock
                )
            )
            
    CycleCountItem.objects.bulk_create(cc_items_to_create)
    return cc_task

@transaction.atomic
def record_cycle_count_item(task_id, bin_id, sku_id, counted_qty, user):
    """
    Cycle Count ki quantity record karta hai aur zarurat padne par inventory adjust karta hai.
    InventoryStock update ko signal se badla.
    """
    
    cc_item = CycleCountItem.objects.select_for_update().get(
        task_id=task_id, 
        bin_id=bin_id, 
        sku_id=sku_id
    )

    if cc_item.counted_qty is not None:
        raise ValueError("This item has already been counted.")
        
    cc_item.counted_qty = counted_qty
    
    # Adjustment ki zaroorat hai?
    delta = counted_qty - cc_item.expected_qty
    cc_item.adjusted = (delta != 0)
    
    if delta != 0:
        # 1. BinInventory adjust (WMS internal model - remains)
        bi = BinInventory.objects.get(bin_id=bin_id, sku_id=sku_id)
        bi.qty += delta # (agar delta positive hai toh add hoga, negative hai toh subtract)
        bi.save(update_fields=['qty'])
        
        # 2. InventoryStock adjust - DIRECT WRITE HATAAYEIN, SIGNAL BHEJEIN
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=sku_id,
            warehouse_id=cc_item.task.warehouse.id,
            delta_available=delta,
            delta_reserved=0,
            reference=str(cc_item.task.id),
            change_type='cycle_count_adjustment'
        )
        
        # 3. StockMovement log (remains)
        warehouse = cc_item.task.warehouse
        StockMovement.objects.create(
            sku_id=sku_id, warehouse=warehouse, bin_id=bin_id,
            change_type="cycle_count_adjustment", delta_qty=delta, reference_id=str(cc_item.task.id)
        )
        
    cc_item.save(update_fields=['counted_qty', 'adjusted'])
    
    # Check if task is complete
    if cc_item.task.items.filter(counted_qty__isnull=True).count() == 0:
        cc_item.task.status = 'completed'
        cc_item.task.save(update_fields=['status'])

    return cc_item