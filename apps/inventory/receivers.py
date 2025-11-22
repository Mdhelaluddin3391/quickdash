# apps/inventory/receivers.py
import logging
from django.dispatch import receiver

from apps.warehouse.signals import inventory_change_required
from .tasks import update_inventory_stock_task

logger = logging.getLogger(__name__)


@receiver(inventory_change_required)
def handle_inventory_change_signal(
    sender,
    sku_id,
    warehouse_id,
    delta_available,
    delta_reserved,
    reference,
    change_type,
    **kwargs,
):
    """
    Warehouse app se inventory_change_required signal receive karta hai.

    - THIS is the only entry point for physical stock → central inventory.
    - Currently hum synchronous task call use kar rahe hain
      taaki race conditions na aaye.

    Microservice style:
    - In future, yahan .delay(...) use karke async bhi kar sakte ho,
      agar eventual consistency tolerate karni ho.
    """
    logger.info(
        "INVENTORY SIGNAL: Ref=%s, Type=%s, SKU=%s, WH=%s, ΔAvl=%s, ΔRes=%s",
        reference,
        change_type,
        sku_id,
        warehouse_id,
        delta_available,
        delta_reserved,
    )

    # Strong consistency mode → direct call
    update_inventory_stock_task.delay(
        sku_id=str(sku_id),
        warehouse_id=str(warehouse_id),
        delta_available=delta_available,
        delta_reserved=delta_reserved,
        reference=reference,
        change_type=change_type,
    )
    # Async mode (optional future):
    # update_inventory_stock_task.delay(
    #     str(sku_id), str(warehouse_id), delta_available, delta_reserved,
    #     reference=reference, change_type=change_type
    # )
