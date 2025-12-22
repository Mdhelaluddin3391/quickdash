import logging
from django.db import transaction
from django.utils import timezone
from django.db.models import F
from apps.utils.exceptions import BusinessLogicException
from apps.inventory.services import InventoryService
from apps.utils.utils import generate_code
from .models import Warehouse, PickingTask, PickItem, BinInventory, PackingTask, DispatchRecord

logger = logging.getLogger(__name__)

class WarehouseOpsService:
    @staticmethod
    @transaction.atomic
    def generate_picking_task(order_id: str, warehouse_id: str, items: list):
        warehouse = Warehouse.objects.get(id=warehouse_id)
        task = PickingTask.objects.create(
            order_id=order_id,
            warehouse=warehouse,
            status=PickingTask.Status.PENDING
        )

        pick_items = []
        
        for item in items:
            sku_id = item['product_id']
            qty_needed = item['quantity']
            
            # [FIX] Filter bins that have UNRESERVED quantity > 0
            # We calculate available = quantity - reserved_qty
            available_bins = BinInventory.objects.select_for_update().filter(
                bin__zone__warehouse=warehouse,
                sku_id=sku_id
            ).annotate(
                available=F('quantity') - F('reserved_qty')
            ).filter(available__gt=0).order_by('quantity')

            qty_allocated = 0
            
            for bin_inv in available_bins:
                if qty_allocated >= qty_needed:
                    break
                
                # Double check available after lock
                # (Note: annotate value isn't refreshed by select_for_update automatically in older Django, 
                # so we recalculate explicitly for safety)
                real_available = bin_inv.quantity - bin_inv.reserved_qty
                if real_available <= 0:
                    continue

                take = min(real_available, qty_needed - qty_allocated)
                
                # [CRITICAL FIX] Reserve NOW to prevent race condition
                bin_inv.reserved_qty = F('reserved_qty') + take
                bin_inv.save(update_fields=['reserved_qty'])
                
                pick_items.append(PickItem(
                    task=task,
                    sku_id=sku_id,
                    bin=bin_inv.bin,
                    qty_to_pick=take,
                    picked_qty=0
                ))
                qty_allocated += take
            
            if qty_allocated < qty_needed:
                logger.error(f"Shortage for Order {order_id} SKU {sku_id}. Allocated: {qty_allocated}/{qty_needed}")

        PickItem.objects.bulk_create(pick_items)
        return task

    @staticmethod
    @transaction.atomic
    def scan_pick(task_id: str, pick_item_id: str, qty: int, user):
        pick_item = PickItem.objects.select_for_update().get(id=pick_item_id, task_id=task_id)
        
        if pick_item.is_picked:
            raise BusinessLogicException("Item already picked.")
        
        if qty != pick_item.qty_to_pick:
            raise BusinessLogicException(f"Incorrect quantity. Expected {pick_item.qty_to_pick}")

        bin_inv = BinInventory.objects.select_for_update().get(bin=pick_item.bin, sku=pick_item.sku)
        
        # [CRITICAL FIX] Release Reservation & Deduct Quantity
        # We perform both operations atomically.
        if bin_inv.quantity < qty:
             raise BusinessLogicException("Physical bin shortage!")

        bin_inv.quantity = F('quantity') - qty
        bin_inv.reserved_qty = F('reserved_qty') - qty
        bin_inv.save(update_fields=['quantity', 'reserved_qty'])

        pick_item.picked_qty = qty
        pick_item.is_picked = True
        pick_item.save(update_fields=['picked_qty', 'is_picked'])

        WarehouseOpsService._check_picking_completion(pick_item.task)
        return pick_item

    @staticmethod
    def _check_picking_completion(task):
        if not task.items.filter(is_picked=False).exists():
            task.status = PickingTask.Status.COMPLETED
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            
            PackingTask.objects.create(picking_task=task, status=PackingTask.Status.PENDING)

    @staticmethod
    @transaction.atomic
    def complete_packing(packing_task_id: str, user):
        pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
        
        if pack_task.status == PackingTask.Status.COMPLETED:
            raise BusinessLogicException("Already packed.")

        pack_task.status = PackingTask.Status.COMPLETED
        pack_task.packer = user
        pack_task.save(update_fields=['status', 'packer'])

        picking_task = pack_task.picking_task
        dispatch = DispatchRecord.objects.create(
            picking_task=picking_task,
            warehouse=picking_task.warehouse,
            order_id=picking_task.order_id,
            status=DispatchRecord.Status.READY,
            pickup_otp=generate_code()[:4]
        )

        picked_items = [{"product_id": pi.sku.id, "quantity": pi.picked_qty} for pi in picking_task.items.all()]

        InventoryService.confirm_deduction(
            warehouse_id=picking_task.warehouse.id,
            items=picked_items,
            reference=f"DISPATCH-{dispatch.id}"
        )
        
        # Trigger Delivery Assignment Here
        from apps.delivery.services import DeliveryService
        from apps.orders.models import Order
        order = Order.objects.get(id=picking_task.order_id)
        DeliveryService.create_delivery_job(order)

        return dispatch