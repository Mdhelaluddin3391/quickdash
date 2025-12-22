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
    Cancels orders pending for > 15 minutes, BUT double-checks payment status first.
    """
    cutoff = timezone.now() - timedelta(minutes=15)
    
    pending_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lt=cutoff
    )
    
    count = 0
    # Import inside task to ensure app registry is ready
    from apps.payments.services import PaymentService
    from apps.orders.services import OrderService 
    
    for order in pending_orders:
        try:
            # [SAFETY GUARD] Poll Gateway before killing the order
            is_paid_actually = PaymentService.sync_payment_status(order)
            
            if is_paid_actually:
                logger.info(f"Auto-Cancel Aborted: Order {order.id} was actually paid. Synced successfully.")
                continue

            # If still pending after poll, it is genuinely unpaid. Cancel it.
            OrderService.cancel_order(order.id, reason="Payment Timeout")
            count += 1
            
        except Exception as e:
            logger.error(f"Failed to auto-cancel order {order.id}: {e}")

    return f"Auto-cancelled {count} orders"