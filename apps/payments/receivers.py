# apps/payments/receivers.py
import logging
from django.dispatch import receiver

from apps.orders.signals import order_refund_requested
from .tasks import process_order_refund_task

logger = logging.getLogger(__name__)


@receiver(order_refund_requested)
def handle_order_refund_request(sender, order_id, amount, reason, **kwargs):
    """
    Orders app se refund request signal sunta hai aur Celery task ko delegate karta hai.
    """
    logger.info(
        "Received order_refund_requested signal for Order ID: %s. Delegating to Celery.",
        order_id,
    )

    process_order_refund_task.delay(
        order_id=str(order_id),
        amount=str(amount),
        reason=reason,
    )
