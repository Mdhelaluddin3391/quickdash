# apps/payments/tasks.py (NEW FILE)
from celery import shared_task
from celery.utils.log import get_task_logger
from apps.orders.models import Order 
from .services import process_order_refund # Service function ko reuse karein

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_order_refund_task(self, order_id, amount=None, reason=""):
    """
    Background task to process refund requests received via signal/API.
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # Core business logic service ko call karein
        success = process_order_refund(order, amount=amount, reason=reason)
        
        if not success:
            logger.warning(f"Refund processing returned False for order {order_id}. Retrying...")
            raise self.retry() # Agar service fail ho to retry karein
            
        return f"Refund successfully processed for order {order_id}"
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for refund.")
        return f"Order {order_id} not found."
    except Exception as exc:
        logger.exception(f"Refund task failed for order {order_id}.")
        # Retry logic Celery task mein hi hona chahiye
        raise self.retry(exc=exc)