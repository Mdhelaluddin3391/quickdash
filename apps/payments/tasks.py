from celery import shared_task
from .services import PaymentService
from apps.orders.models import Order
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def process_refund_task(self, order_id):
    """
    Retries refunds in background if Gateway is flaky.
    """
    try:
        order = Order.objects.get(id=order_id)
        PaymentService.initiate_refund(order)
    except Exception as e:
        logger.error(f"Refund retry failed for {order_id}: {e}")
        raise self.retry(exc=e)