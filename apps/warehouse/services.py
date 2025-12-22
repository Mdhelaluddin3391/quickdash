# apps/warehouse/services.py

from django.db import transaction
from django.utils import timezone

from apps.inventory.services import InventoryService
from apps.orders.models import Order, OrderStatus

from .models import PickingTask, PickItem, BinInventory


class WarehouseService:

    @staticmethod
    @transaction.atomic
    def complete_picking_task(task_id: str, picked_items: list):
        """
        Picking SUCCESS → Physical stock gone → Logical stock MUST update.
        """
        task = PickingTask.objects.select_for_update().get(id=task_id)

        if task.is_completed:
            return task

        order = task.order
        warehouse = task.warehouse

        # 1️⃣ Deduct PHYSICAL stock (BinInventory)
        for item in picked_items:
            bin_inv = BinInventory.objects.select_for_update().get(
                bin_id=item["bin_id"],
                product_id=item["product_id"],
            )
            bin_inv.quantity -= item["quantity"]
            bin_inv.save(update_fields=["quantity"])

        # 2️⃣ Sync LOGICAL inventory (FINAL COMMIT)
        InventoryService.confirm_deduction(
            warehouse_id=warehouse.id,
            items=[
                {
                    "product_id": i["product_id"],
                    "quantity": i["quantity"],
                }
                for i in picked_items
            ],
            reference=f"ORDER-{order.order_id}",
        )

        # 3️⃣ Update Order state
        order.status = OrderStatus.READY_FOR_DELIVERY
        order.save(update_fields=["status"])

        task.is_completed = True
        task.completed_at = timezone.now()
        task.save(update_fields=["is_completed", "completed_at"])

        return task
