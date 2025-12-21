from celery import shared_task
import razorpay
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@shared_task(name="process_razorpay_refund")
def process_razorpay_refund_task(payment_id, is_partial_refund=False, amount=None):
    from apps.payments.models import Payment

    try:
        payment = Payment.objects.get(id=payment_id)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        refund_amount_paise = None
        if amount:
            refund_amount_paise = int(float(amount) * 100)
        elif not is_partial_refund:
            refund_amount_paise = int(payment.amount * 100)

        refund_data = {
            "payment_id": payment.transaction_id,
            "notes": {"reason": "Order Cancelled via QuickDash App"}
        }
        if refund_amount_paise:
            refund_data["amount"] = refund_amount_paise

        refund = client.payment.refund(payment.transaction_id, refund_data)
        
        payment.status = 'REFUNDED'
        payment.refund_id = refund.get('id')
        payment.save()
        
        logger.info(f"Refund Successful for Payment {payment_id}. Refund ID: {refund.get('id')}")
        return f"Refund Processed: {refund.get('id')}"

    except Exception as e:
        logger.exception(f"Refund Failed for Payment {payment_id}: {e}")
        return f"Refund Failed: {e}"


# FIX: Removed explicit name="auto_cancel_unpaid_orders" to match settings.py path
@shared_task
def auto_cancel_unpaid_orders():
    """
    Optimized batch cancellation. 
    Only looks for orders created within a specific window to avoid full table scans.
    """
    from apps.orders.models import Order
    from apps.orders.services import cancel_order
    
    # Configuration
    cancellation_window = getattr(settings, 'ORDER_CANCELLATION_WINDOW', 300) # Default 5 mins
    
    # Time thresholds
    now = timezone.now()
    cutoff_time = now - timedelta(seconds=cancellation_window)
    # Safety buffer: Don't process orders older than 24 hours (assume handled or manual intervention)
    safety_buffer = now - timedelta(hours=24)

    # 1. Fetch Candidates (Using Index on created_at and status)
    orders_to_cancel = Order.objects.filter(
        status='pending',
        payment_status='pending',
        created_at__lte=cutoff_time,
        created_at__gte=safety_buffer 
    ).only('id', 'warehouse_id', 'status')[:100] # Batch limit for memory safety

    if not orders_to_cancel:
        return "No expired orders."

    count = 0
    for order in orders_to_cancel:
        # Atomic cancellation service
        success, msg = cancel_order(order, cancelled_by='SYSTEM', reason='Payment timeout')
        if success:
            count += 1
            logger.info(f"Auto-cancelled Order {order.id}")
        else:
            logger.warning(f"Failed to auto-cancel Order {order.id}: {msg}")

    # If we hit the limit, re-trigger immediately to clear backlog
    if len(orders_to_cancel) == 100:
        auto_cancel_unpaid_orders.delay()

    return f"Cancelled {count} orders."