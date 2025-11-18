# apps/payments/receivers.py
import logging
from django.dispatch import receiver
from apps.orders.signals import order_refund_requested # Orders app se signal import
from .tasks import process_order_refund_task

logger = logging.getLogger(__name__)

@receiver(order_refund_requested)
def handle_order_refund_request(sender, order_id, amount, reason, **kwargs):
    """
    Orders app se refund request signal sunta hai aur Celery task ko delegate karta hai.
    """
    logger.info(f"Received order_refund_requested signal for Order ID: {order_id}. Delegating to Celery.")
    
    # Task ko asynchronously call karein
    process_order_refund_task.delay(
        order_id=str(order_id),
        amount=amount,
        reason=reason
    )