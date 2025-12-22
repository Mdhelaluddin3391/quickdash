from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from .models import Order
from .services import OrderService

logger = logging.getLogger("django")

@shared_task
def auto_cancel_unpaid_orders():
    """
    Runs every 5 minutes.
    Cancels orders pending for > 15 minutes to release stock.
    """
    cutoff = timezone.now() - timedelta(minutes=15)
    
    pending_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lt=cutoff
    )
    
    count = 0
    for order in pending_orders:
        try:
            # Service handles stock release
            OrderService.cancel_order(order.id, reason="Payment Timeout")
            count += 1
        except Exception as e:
            logger.error(f"Failed to auto-cancel order {order.id}: {e}")

    return f"Auto-cancelled {count} orders"