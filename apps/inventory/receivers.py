import logging
from django.dispatch import receiver
from django.db import transaction
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
    Robust signal handler.
    Guarantees task scheduling only after the Warehouse transaction commits.
    """
    
    def _schedule_task():
        try:
            # Use delay() to offload to Celery
            update_inventory_stock_task.delay(
                sku_id=str(sku_id),
                warehouse_id=str(warehouse_id),
                delta_available=int(delta_available),
                delta_reserved=int(delta_reserved),
                reference=str(reference),
                change_type=str(change_type)
            )
            logger.info(f"Inventory update queued for SKU {sku_id} @ WH {warehouse_id}")
        except Exception as e:
            # This runs in the web process, so we log critical errors
            logger.critical(
                f"FAILED to queue inventory update! Ref: {reference}. Error: {e}", 
                exc_info=True
            )

    # Only run if the transaction causing this signal successfully commits
    transaction.on_commit(_schedule_task)