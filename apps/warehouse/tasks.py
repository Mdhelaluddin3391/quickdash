from celery import shared_task
from .services import WarehouseOpsService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_warehouse_order_task(self, order_id, warehouse_id, items):
    """
    Triggered when an Order is CONFIRMED (PAID).
    Generates Picking Tasks.
    """
    try:
        WarehouseOpsService.generate_picking_task(order_id, warehouse_id, items)
        logger.info(f"Picking Task generated for Order {order_id}")
    except Exception as e:
        logger.exception(f"Failed to generate picking task for {order_id}")
        raise self.retry(exc=e, countdown=60)