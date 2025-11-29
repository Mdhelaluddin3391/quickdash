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
    Transactional integration between Warehouse (Physical) and Inventory (Logical).
    Ensures inventory updates only happen if the warehouse transaction commits.
    """
    logger.info(
        "INVENTORY SIGNAL: Ref=%s, Type=%s, SKU=%s, WH=%s",
        reference, change_type, sku_id, warehouse_id
    )

    # Helper function to execute the update
    def _do_update():
        # Call the task synchronously or asynchronously depending on configuration.
        # Ideally, this runs after the physical movement is committed.
        try:
            update_inventory_stock_task(
                sku_id=str(sku_id),
                warehouse_id=str(warehouse_id),
                delta_available=delta_available,
                delta_reserved=delta_reserved
            )
        except Exception as e:
            logger.critical(f"INVENTORY SYNC FAILED after commit! Manual Reconcile needed for SKU {sku_id} in WH {warehouse_id}. Error: {e}")

    # Hook into the transaction commit lifecycle
    # If the main transaction rolls back, this will NOT run, preventing phantom stock updates.
    transaction.on_commit(_do_update)