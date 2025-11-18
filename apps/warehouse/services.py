import random
from django.db import transaction, models
from django.utils import timezone
from .models import (
    Warehouse, Bin, BinInventory, StockMovement, 
    PickingTask, PickItem, PackingTask, DispatchRecord
)
from apps.inventory.models import InventoryStock
from .exceptions import OutOfStockError, ReservationFailedError
from .signals import dispatch_ready_for_delivery

@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items):
    """
    Order aane par stock reserve karta hai:
    1. Aggregate Inventory (Inventory App) update karta hai.
    2. Physical Bins (WMS App) mein stock lock karta hai.
    """
    allocations = {}
    warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

    for it in items:
        sku_id = it["sku_id"]
        qty_needed = int(it["qty"])

        # 1. Check Aggregate Stock (Fast Check)
        try:
            inv = InventoryStock.objects.select_for_update().get(warehouse=warehouse, sku_id=sku_id)
        except InventoryStock.DoesNotExist:
            raise OutOfStockError(f"SKU {sku_id} not found in warehouse.")
            
        if inv.available_qty < qty_needed:
            raise OutOfStockError(f"Not enough stock for SKU {sku_id}. Need {qty_needed}, Have {inv.available_qty}")

        # 2. Reserve from Bins (Physical Allocation)
        # Logic: Jin bins mein sabse zyada maal hai, wahin se uthao (optimize picker route later)
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

        # 3. Update Aggregate
        inv.available_qty -= qty_needed
        inv.reserved_qty += qty_needed
        inv.save()

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
        PackingTask.objects.create(picking_task=task, status="pending")
        
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
        # Bin Inventory Update
        bi = BinInventory.objects.get(bin=pitem.bin, sku=pitem.sku)
        bi.qty -= pitem.qty
        bi.reserved_qty -= pitem.qty # Reservation free kar do
        bi.save()
        
        # Aggregate Inventory Update
        inv = InventoryStock.objects.get(warehouse=warehouse, sku=pitem.sku)
        inv.reserved_qty -= pitem.qty # Sold!
        inv.save()
        
        # Log
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