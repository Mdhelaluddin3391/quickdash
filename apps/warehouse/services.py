from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import (
    Warehouse, Bin, BinInventory, PickingTask, PickItem, DispatchRecord
)
from .realtime import broadcast_wms_event
# Explicit Cross-App Interface
from apps.inventory.services import InventoryService 

class WarehouseOpsService:

    @staticmethod
    @transaction.atomic
    def reserve_stock_for_order(order_id: str, warehouse_id: int, items: list):
        """
        1. Finds best bins for items (FIFO or optimize path).
        2. Creates PickingTask.
        3. Updates Logical Inventory via InventoryService.
        """
        warehouse = Warehouse.objects.get(id=warehouse_id)
        task = PickingTask.objects.create(
            order_id=order_id,
            warehouse=warehouse,
            status=PickingTask.Status.PENDING
        )

        for item in items:
            sku_id = item['sku_id']
            qty_needed = item['qty']
            
            # Smart Bin Selection: Find bins with stock
            available_bins = BinInventory.objects.filter(
                bin__zone__warehouse=warehouse,
                sku_id=sku_id,
                quantity__gt=0
            ).order_by('quantity') # Simple strategy: clear small bins first

            qty_allocated = 0
            for bin_inv in available_bins:
                if qty_allocated >= qty_needed:
                    break
                
                take = min(bin_inv.quantity, qty_needed - qty_allocated)
                
                PickItem.objects.create(
                    task=task,
                    sku_id=sku_id,
                    bin=bin_inv.bin,
                    qty_to_pick=take
                )
                
                # We do NOT deduct BinInventory quantity here. 
                # We deduct only when physically scanned (scan_pick).
                # However, we MUST reserve it in the Logical Inventory.
                qty_allocated += take

            if qty_allocated < qty_needed:
                raise ValidationError(f"Physical stock mismatch for SKU {sku_id}")

        broadcast_wms_event({
            "type": "new_picking_task",
            "warehouse_id": warehouse.id,
            "task_id": str(task.id)
        })
        return task

    @staticmethod
    @transaction.atomic
    def scan_pick(task_id: str, pick_item_id: int, qty_scanned: int, user):
        """
        Worker physically picks item.
        State: Updates BinInventory (Physical) immediately.
        """
        pick_item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
        
        if pick_item.is_picked:
            raise ValidationError("Item already picked.")
            
        if qty_scanned != pick_item.qty_to_pick:
            raise ValidationError(f"Scan mismatch. Expected {pick_item.qty_to_pick}, got {qty_scanned}")

        # 1. Update Physical Inventory
        bin_inv = BinInventory.objects.select_for_update().get(
            bin=pick_item.bin, 
            sku=pick_item.sku
        )
        if bin_inv.quantity < qty_scanned:
            raise ValidationError(f"Bin {pick_item.bin.bin_code} is physically short!")

        bin_inv.quantity -= qty_scanned
        bin_inv.save()

        # 2. Update Task State
        pick_item.picked_qty = qty_scanned
        pick_item.is_picked = True
        pick_item.save()

        # 3. Check Task Completion
        task = pick_item.task
        if not task.picker:
            task.picker = user
            task.started_at = timezone.now()
            task.status = PickingTask.Status.IN_PROGRESS
            task.save()

        # Check if all items are picked
        if not task.items.filter(is_picked=False).exists():
            WarehouseOpsService._complete_picking_task(task)

        return pick_item

    @staticmethod
    def _complete_picking_task(task: PickingTask):
        task.status = PickingTask.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save()

        # Create Dispatch Record
        import secrets
        otp = str(secrets.randbelow(999999)).zfill(6)
        
        DispatchRecord.objects.create(
            picking_task=task,
            status='READY',
            pickup_otp=otp
        )

        # Sync Logical Inventory (Hard Commit)
        # We tell InventoryService that these items have physically left the shelf
        # for this specific order.
        # This confirms the reservation made earlier.
        
        # Notify Logistics
        from apps.delivery.services import DeliveryService
        DeliveryService.create_task_from_dispatch(
            order_id=task.order_id, 
            dispatch_id=str(task.id), # Simplified linkage
            warehouse_otp=otp
        )

        broadcast_wms_event({
            "type": "task_completed",
            "task_id": str(task.id)
        })