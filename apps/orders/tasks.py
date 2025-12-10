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
    """Auto-cancel orders stuck in pending/payment states beyond allowed window."""
    from apps.orders.models import Order
    from apps.orders.services import cancel_order

    cutoff_minutes = getattr(settings, 'AUTO_CANCEL_PENDING_MINUTES', 30)
    cutoff = timezone.now() - timedelta(minutes=cutoff_minutes)

    orders = Order.objects.filter(
        status='pending',
        payment_status='pending',
        created_at__lte=cutoff
    )

    count = 0
    for order in orders:
        ok, msg = cancel_order(order, cancelled_by='SYSTEM', reason='Auto-cancel unpaid order')
        if ok:
            count += 1
            logger.info(f"Auto-cancelled order {order.id}")
        else:
            logger.warning(f"Failed to auto-cancel order {order.id}: {msg}")

    return f"Auto-cancelled {count} orders"