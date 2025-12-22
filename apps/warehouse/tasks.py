from celery import shared_task
from .services import WarehouseOpsService
import logging

logger = logging.getLogger(__name__)

@shared_task
def allocate_stock_task(order_id, warehouse_id, items):
    """
    Async task to allocate stock for an order.
    Triggered by Order Created signal.
    """
    try:
        WarehouseOpsService.reserve_stock_for_order(order_id, warehouse_id, items)
        logger.info(f"Stock allocated for Order {order_id}")
    except Exception as e:
        logger.error(f"Allocation failed for Order {order_id}: {e}")
        # Logic to auto-cancel order or flag for manual review
        # apps.orders.services.OrderService.mark_allocation_failed(order_id)