from django.dispatch import receiver
from apps.orders.signals import send_order_created
from .tasks import process_warehouse_order_task
import logging

logger = logging.getLogger(__name__)

@receiver(send_order_created)
def handle_order_created(sender, order_id, order_items, warehouse_id, **kwargs):
    """
    Listens for order creation (Payment Confirmed) and starts Warehouse flow.
    """
    logger.info(f"Order {order_id} received in Warehouse {warehouse_id}")
    process_warehouse_order_task.delay(
        order_id=str(order_id),
        warehouse_id=str(warehouse_id),
        items=order_items
    )