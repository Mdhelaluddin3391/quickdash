from django.db import transaction
from .models import Warehouse, BinInventory, StockMovement, PickingTask, PickItem
from django.core.exceptions import ValidationError
# apps/warehouse/services.py (Append this code at the bottom)

from django.db.models import Q
from apps.accounts.models import StoreStaffProfile
from django.utils import timezone


@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items_needed):
    """
    GREEDY ALLOCATION LOGIC:
    Agar user ko 10 items chahiye:
    - Bin A mein 4 hain -> Lock 4
    - Bin B mein 6 hain -> Lock 6
    - Total 10 reserved.
    """
    allocations = []
    warehouse = Warehouse.objects.get(id=warehouse_id)
    
    # Picking Task Create karo (Staff ke liye)
    task = PickingTask.objects.create(order_id=order_id, warehouse=warehouse, status='PENDING')

    for item in items_needed:
        sku_id = item['sku_id']
        qty_needed = item['qty']
        
        # 1. Sabhi Bins dhoondo jahan ye SKU hai, zyada stock wale pehle (Optimization)
        available_bins = BinInventory.objects.select_for_update().filter(
            bin__zone__warehouse=warehouse,
            sku_id=sku_id,
            qty__gt=models.F('reserved_qty') # Sirf wahan jahan Available > 0 hai
        ).order_by('-qty') # Greedy approach (pick from largest pile first)

        qty_remaining = qty_needed

        for bin_inv in available_bins:
            if qty_remaining <= 0:
                break
            
            # Kitna le sakte hain is bin se?
            available = bin_inv.available_qty
            to_take = min(available, qty_remaining)
            
            # 2. Reserve karo (Lock Logic)
            bin_inv.reserved_qty += to_take
            bin_inv.save()
            
            # 3. PickItem Task mein add karo
            PickItem.objects.create(
                task=task,
                sku_id=sku_id,
                bin=bin_inv.bin,
                qty_to_pick=to_take
            )

            # 4. Movement Record karo
            StockMovement.objects.create(
                sku_id=sku_id,
                warehouse=warehouse,
                bin=bin_inv.bin,
                qty_change=-to_take,
                movement_type='RESERVE',
                reference_id=str(order_id)
            )
            
            qty_remaining -= to_take

        if qty_remaining > 0:
            # Agar abhi bhi stock kam pad raha hai
            raise ValidationError(f"Not enough stock for SKU {sku_id}. Missing {qty_remaining}")

    return task

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
                task=task, sku_id=sku_id, bin_id=alloc["bin_id"], qty=alloc["qty"]
            )
    return task

@transaction.atomic
def scan_pick(task_id, pick_item_id, qty_scanned, user):
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
    
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
        task.picker = user
        task.save()

    if not task.items.filter(picked_qty__lt=models.F('qty')).exists():
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()
        packing_task, _ = PackingTask.objects.get_or_create(picking_task=task, defaults={"status": "pending"})
        notify_packer_new_task(packing_task)
        
    return item

@transaction.atomic
def complete_packing(packing_task_id, packer_user):
    pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
    pack_task.packer = packer_user
    pack_task.status = "packed"
    pack_task.save()
    
    picking_task = pack_task.picking_task
    warehouse = picking_task.warehouse
    
    for pitem in picking_task.items.all():
        bi = BinInventory.objects.get(bin=pitem.bin, sku=pitem.sku)
        bi.qty -= pitem.qty
        bi.reserved_qty -= pitem.qty
        bi.save()
        
        inventory_change_required.send(
            sender=Warehouse,
            sku_id=str(pitem.sku_id),
            warehouse_id=str(warehouse.id),
            delta_available=0, 
            delta_reserved=-pitem.qty, 
            reference=str(picking_task.order_id),
            change_type='sale_dispatch'
        )
        
        StockMovement.objects.create(
            sku=pitem.sku, warehouse=warehouse, bin=pitem.bin,
            change_type="sale_dispatch", delta_qty=-pitem.qty, reference_id=str(picking_task.order_id)
        )

    pickup_otp = "".join(str(random.randint(0, 9)) for _ in range(4))
    dispatch = DispatchRecord.objects.create(
        packing_task=pack_task, warehouse=warehouse, order_id=picking_task.order_id,
        status="ready", pickup_otp=pickup_otp
    )
    
    dispatch_ready_for_delivery.send(
        sender=DispatchRecord, dispatch_id=dispatch.id, order_id=dispatch.order_id,
        warehouse_id=warehouse.id, pickup_otp=pickup_otp
    )
    return dispatch

@transaction.atomic
def mark_pickitem_skipped(task_id, pick_item_id, user, reason: str, reopen_for_picker=False):
    item = PickItem.objects.select_for_update().get(id=pick_item_id, task__id=task_id)
    if item.picked_qty >= item.qty: raise ValueError("This item is already fully picked.")
    if item.skips.filter(is_resolved=False).exists(): raise ValueError("Item is already skipped.")

    return PickSkip.objects.create(
        task=item.task, pick_item=item, skipped_by=user,
        reason=reason, reopen_after_scan=reopen_for_picker
    )

@transaction.atomic
def resolve_skip_as_shortpick(skip: PickSkip, resolved_by_user, note: str):
    if skip.is_resolved: raise ValueError("Skip already resolved.")
    item = skip.pick_item
    qty_needed = item.qty - item.picked_qty
    if qty_needed <= 0:
        skip.is_resolved = True
        skip.save(update_fields=['is_resolved'])
        raise ValueError("No quantity pending.")
        
    spi = ShortPickIncident.objects.create(
        skip=skip, resolved_by=resolved_by_user,
        short_picked_qty=qty_needed, notes=note
    )

    bi = BinInventory.objects.get(bin=item.bin, sku=item.sku)
    bi.reserved_qty -= qty_needed
    bi.save(update_fields=['reserved_qty'])
    
    inventory_change_required.send(
        sender=Warehouse, sku_id=str(item.sku_id), warehouse_id=str(item.task.warehouse.id),
        delta_available=qty_needed, delta_reserved=-qty_needed,
        reference=str(item.task.order_id), change_type='short_pick_rollback'
    )
   
    skip.is_resolved = True
    skip.save(update_fields=['is_resolved'])
    
    StockMovement.objects.create(
        sku=item.sku, warehouse=item.task.warehouse, bin=item.bin,
        change_type="short_pick_rollback", delta_qty=qty_needed, reference_id=str(item.task.order_id)
    )
    return spi

@transaction.atomic
def admin_fulfillment_cancel(pick_item: PickItem, cancelled_by_user, reason: str):
    """
    Corrected: UUIDs converted to string for robustness.
    """
    if pick_item.qty == pick_item.picked_qty: raise ValueError("Cannot cancel fully picked item.")
    qty_to_cancel = pick_item.qty - pick_item.picked_qty
    
    fc_record = FulfillmentCancel.objects.create(
        pick_item=pick_item, cancelled_by=cancelled_by_user,
        reason=reason, refund_initiated=True 
    )
    
    bi = BinInventory.objects.get(bin=pick_item.bin, sku=pick_item.sku)
    bi.reserved_qty -= qty_to_cancel
    bi.save(update_fields=['reserved_qty'])
    
    inventory_change_required.send(
        sender=Warehouse, sku_id=str(pick_item.sku_id), warehouse_id=str(pick_item.task.warehouse.id),
        delta_available=qty_to_cancel, delta_reserved=-qty_to_cancel,
        reference=str(pick_item.task.order_id), change_type='fulfillment_cancel_rollback'
    )

    pick_item.qty = pick_item.picked_qty
    pick_item.save(update_fields=['qty'])

    # CRITICAL FIX: UUIDs to String conversion
    item_fulfillment_cancelled.send(
        sender=FulfillmentCancel,
        order_id=str(pick_item.task.order_id),
        sku_id=str(pick_item.sku_id),
        qty=qty_to_cancel,
        reason=reason
    )

    return fc_record

# ... (create_grn_and_putaway, place_putaway_item etc. remain same but ensure string conversions if emitting signals)

@transaction.atomic
def create_grn_and_putaway(warehouse_id, grn_number, items, created_by):
    warehouse = Warehouse.objects.get(id=warehouse_id)
    grn = GRN.objects.create(
        warehouse=warehouse, grn_number=grn_number,
        status="received", created_by=created_by
    )
    grn_items = [
        GRNItem(grn=grn, sku_id=item['sku_id'], expected_qty=item['qty'], received_qty=item['qty'])
        for item in items
    ]
    GRNItem.objects.bulk_create(grn_items)
    putaway_task = PutawayTask.objects.create(grn=grn, warehouse=warehouse, status="pending")
    putaway_items = [PutawayItem(task=putaway_task, grn_item=g_item) for g_item in grn_items]
    PutawayItem.objects.bulk_create(putaway_items)
    return grn, putaway_task

@transaction.atomic
def place_putaway_item(task_id, putaway_item_id, bin_id, qty_placed, user):
    item = PutawayItem.objects.select_for_update().get(id=putaway_item_id, task__id=task_id)
    grn_item = item.grn_item
    if item.placed_qty + qty_placed > grn_item.received_qty: raise ValueError("Over placement.")

    bin_obj = Bin.objects.get(id=bin_id)
    warehouse = item.task.warehouse
    sku = grn_item.sku
    
    bi, _ = BinInventory.objects.get_or_create(bin=bin_obj, sku=sku, defaults={'qty': 0})
    bi.qty += qty_placed
    bi.save(update_fields=['qty'])

    inventory_change_required.send(
        sender=Warehouse, sku_id=str(sku.id), warehouse_id=str(warehouse.id),
        delta_available=qty_placed, delta_reserved=0,
        reference=grn_item.grn.grn_number, change_type='putaway'
    )
    
    item.placed_qty += qty_placed
    item.placed_bin = bin_obj
    item.save(update_fields=['placed_qty', 'placed_bin'])
    
    if item.task.items.aggregate(total=Sum('placed_qty'))['total'] == grn_item.grn.items.aggregate(total=Sum('received_qty'))['total']:
        item.task.status = 'completed'
        item.task.save(update_fields=['status'])
    
    StockMovement.objects.create(
        sku=sku, warehouse=warehouse, bin=bin_obj,
        change_type="putaway", delta_qty=qty_placed, reference_id=grn_item.grn.grn_number
    )
    return item

# ... (create_cycle_count & record_cycle_count_item mein bhi signals mein str() use karein jahan zaroori ho)
@transaction.atomic
def create_cycle_count(warehouse_id, user, sample_bins=None):
    warehouse = Warehouse.objects.get(id=warehouse_id)
    cc_task = CycleCountTask.objects.create(warehouse=warehouse, task_user=user, status='pending')
    
    if sample_bins:
        bins = Bin.objects.filter(id__in=sample_bins)
    else:
        bins = Bin.objects.filter(inventory__qty__gt=0, shelf__aisle__zone__warehouse=warehouse).distinct()[:20] 

    cc_items = []
    for bin_obj in bins:
        for bi in BinInventory.objects.filter(bin=bin_obj, qty__gt=0):
            cc_items.append(CycleCountItem(task=cc_task, bin=bin_obj, sku=bi.sku, expected_qty=bi.qty))
    CycleCountItem.objects.bulk_create(cc_items)
    return cc_task

@transaction.atomic
def record_cycle_count_item(task_id, bin_id, sku_id, counted_qty, user):
    cc_item = CycleCountItem.objects.select_for_update().get(task_id=task_id, bin_id=bin_id, sku_id=sku_id)
    if cc_item.counted_qty is not None: raise ValueError("Already counted.")
        
    cc_item.counted_qty = counted_qty
    delta = counted_qty - cc_item.expected_qty
    cc_item.adjusted = (delta != 0)
    
    if delta != 0:
        bi = BinInventory.objects.get(bin_id=bin_id, sku_id=sku_id)
        bi.qty += delta
        bi.save(update_fields=['qty'])
        
        inventory_change_required.send(
            sender=Warehouse, sku_id=str(sku_id), warehouse_id=str(cc_item.task.warehouse.id),
            delta_available=delta, delta_reserved=0,
            reference=str(cc_item.task.id), change_type='cycle_count_adjustment'
        )
        
        StockMovement.objects.create(
            sku_id=sku_id, warehouse=cc_item.task.warehouse, bin_id=bin_id,
            change_type="cycle_count_adjustment", delta_qty=delta, reference_id=str(cc_item.task.id)
        )
        
    cc_item.save(update_fields=['counted_qty', 'adjusted'])
    if cc_item.task.items.filter(counted_qty__isnull=True).count() == 0:
        cc_item.task.status = 'completed'
        cc_item.task.save(update_fields=['status'])

    return cc_item





def assign_task_to_picker(picking_task):
    """
    ROUND-ROBIN ASSIGNMENT LOGIC:
    1. Sirf unhe dhundo jo 'PICKER' hain aur 'Active' hain.
    2. Unhe sort karo 'last_task_assigned_at' se (jisko sabse pehle kaam mila tha).
    3. Sabse pehle wale ko naya kaam do.
    """
    
    # Available Pickers dhundo (Jo warehouse mein hain)
    available_pickers = StoreStaffProfile.objects.filter(
        role='PICKER',
        is_active_employee=True,
        warehouse_code=picking_task.warehouse.code # Warehouse match hona chahiye
    ).order_by('last_task_assigned_at') # NULL values pehle aayengi (Fresh staff)

    # Agar koi picker mila
    picker_profile = available_pickers.first()
    
    if picker_profile:
        # Task assign karo
        picking_task.picker = picker_profile.user
        picking_task.status = 'PENDING' # Ya 'ASSIGNED'
        picking_task.save()
        
        # Picker ka time update karo taaki agla task kisi aur ko mile (Round Robin)
        picker_profile.last_task_assigned_at = timezone.now()
        picker_profile.save()
        
        return True, f"Assigned to {picker_profile.user.full_name}"
    
    return False, "No available pickers found."