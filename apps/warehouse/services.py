import logging
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import F

from apps.utils.exceptions import BusinessLogicException
from apps.inventory.services import InventoryService
from apps.utils.utils import generate_code

from .models import (
    Warehouse, PickingTask, PickItem, BinInventory, 
    PackingTask, DispatchRecord, Bin
)

logger = logging.getLogger(__name__)

class WarehouseOpsService:
    """
    Central Orchestrator for Physical Warehouse Operations.
    """

    @staticmethod
    @transaction.atomic
    def generate_picking_task(order_id: str, warehouse_id: str, items: list):
        """
        Called by Order Service/Signal.
        Finds bins with stock (FIFO/Logic) and creates tasks.
        """
        warehouse = Warehouse.objects.get(id=warehouse_id)
        task = PickingTask.objects.create(
            order_id=order_id,
            warehouse=warehouse,
            status=PickingTask.Status.PENDING
        )

        pick_items = []
        
        # Simple Logic: Iterate items, find bin with stock
        # Production: This should be a smart algorithm (path optimization)
        for item in items:
            sku_id = item['product_id']
            qty_needed = item['quantity']
            
            # Find bins with this SKU in this warehouse
            # Lock rows to prevent double assignment
            available_bins = BinInventory.objects.select_for_update().filter(
                bin__zone__warehouse=warehouse,
                sku_id=sku_id,
                quantity__gt=0
            ).order_by('quantity') # Pick from smallest piles first to clear bins? Or largest?

            qty_allocated = 0
            
            for bin_inv in available_bins:
                if qty_allocated >= qty_needed:
                    break
                
                take = min(bin_inv.quantity, qty_needed - qty_allocated)
                
                # We do NOT deduct stock yet. We just tell the picker WHERE to go.
                # Deduction happens at SCAN.
                
                pick_items.append(PickItem(
                    task=task,
                    sku_id=sku_id,
                    bin=bin_inv.bin,
                    qty_to_pick=take,
                    picked_qty=0
                ))
                qty_allocated += take
            
            if qty_allocated < qty_needed:
                # Should ideally fail or mark as "Short Pick"
                logger.error(f"Shortage detected for Order {order_id} SKU {sku_id}")
                # For V1: Create task anyway, allow picker to mark missing

        PickItem.objects.bulk_create(pick_items)
        return task

    @staticmethod
    @transaction.atomic
    def scan_pick(task_id: str, pick_item_id: str, qty: int, user):
        """
        Picker scans an item. Physical stock is deducted IMMEDIATELY.
        """
        pick_item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
        
        if pick_item.is_picked:
            raise BusinessLogicException("Item already picked.")
        
        if qty != pick_item.qty_to_pick:
            raise BusinessLogicException(f"Incorrect quantity. Expected {pick_item.qty_to_pick}")

        # 1. Deduct Physical Bin Stock
        bin_inv = BinInventory.objects.select_for_update().get(
            bin=pick_item.bin, 
            sku=pick_item.sku
        )
        
        if bin_inv.quantity < qty:
            raise BusinessLogicException("Physical bin shortage! Please mark as skipped/missing.")

        bin_inv.quantity = F('quantity') - qty
        bin_inv.save(update_fields=['quantity'])

        # 2. Update Pick Item
        pick_item.picked_qty = qty
        pick_item.is_picked = True
        pick_item.save(update_fields=['picked_qty', 'is_picked'])

        # 3. Check Task Completion
        WarehouseOpsService._check_picking_completion(pick_item.task)
        
        return pick_item

    @staticmethod
    def _check_picking_completion(task):
        # Refresh to check all items
        if not task.items.filter(is_picked=False).exists():
            task.status = PickingTask.Status.COMPLETED
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            
            # Auto-create Packing Task
            PackingTask.objects.create(
                picking_task=task,
                status=PackingTask.Status.PENDING
            )

    @staticmethod
    @transaction.atomic
    def complete_packing(packing_task_id: str, user):
        """
        Packer confirms packing. This triggers DISPATCH.
        CRITICAL: This is where we burn the Logical Inventory (InventoryStock).
        """
        pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
        
        if pack_task.status == PackingTask.Status.COMPLETED:
            raise BusinessLogicException("Already packed.")

        pack_task.status = PackingTask.Status.COMPLETED
        pack_task.packer = user
        pack_task.save(update_fields=['status', 'packer'])

        # Create Dispatch Record
        picking_task = pack_task.picking_task
        dispatch = DispatchRecord.objects.create(
            picking_task=picking_task,
            warehouse=picking_task.warehouse,
            order_id=picking_task.order_id,
            status=DispatchRecord.Status.READY,
            pickup_otp=generate_code()[:4] # 4 Digit PIN
        )

        # FINAL SYNC: Burn Logical Inventory
        # We collect what was ACTUALLY picked
        picked_items = []
        for pi in picking_task.items.all():
            picked_items.append({
                "product_id": pi.sku.id,
                "quantity": pi.picked_qty
            })

        InventoryService.confirm_deduction(
            warehouse_id=picking_task.warehouse.id,
            items=picked_items,
            reference=f"DISPATCH-{dispatch.id}"
        )
        
        # Notify Delivery Service (via Signal/Task) requires delivery app to listen
        # For Modular Monolith, we can call Delivery Service directly if needed, 
        # but decouple via Order status update usually.
        # Here we just mark Dispatch Ready. 
        
        return dispatch