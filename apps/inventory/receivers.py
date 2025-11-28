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
    Warehouse app sends signal -> Inventory app updates central stock.
    
    [CRITICAL FIX]: Converted from Async (Celery) to Synchronous.
    This ensures that cart/checkout checks typically see the 
    most up-to-date stock immediately after a reservation/movement.
    """
    logger.info(
        "INVENTORY SIGNAL (SYNC): Ref=%s, Type=%s, SKU=%s, WH=%s, ΔAvl=%s, ΔRes=%s",
        reference,
        change_type,
        sku_id,
        warehouse_id,
        delta_available,
        delta_reserved,
    )

    # DIRECT CALL (No .delay())
    update_inventory_stock_task(
        sku_id=str(sku_id),
        warehouse_id=str(warehouse_id),
        delta_available=delta_available,
        delta_reserved=delta_reserved,
    )