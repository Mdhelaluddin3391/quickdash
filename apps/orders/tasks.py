from celery import shared_task
import razorpay
import logging
from django.conf import settings
from django.db import transaction
from .models import Order, Payment

logger = logging.getLogger(__name__)

@shared_task(name="process_razorpay_refund")
def process_razorpay_refund_task(payment_id, is_partial_refund=False, amount=None):
    """
    Background task jo Razorpay se refund process karta hai.
    Yeh user ko wait nahi karvata.
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        refund_amount_paise = None
        if amount:
            refund_amount_paise = int(float(amount) * 100)
        elif not is_partial_refund:
            # Full refund
            refund_amount_paise = int(payment.amount * 100)

        refund_data = {
            "payment_id": payment.transaction_id,
            "notes": {"reason": "Order Cancelled via QuickDash App"}
        }
        if refund_amount_paise:
            refund_data["amount"] = refund_amount_paise

        # Call Razorpay API
        refund = client.payment.refund(payment.transaction_id, refund_data)
        
        # Update DB
        payment.status = 'REFUNDED'
        payment.refund_id = refund.get('id')
        payment.save()
        
        logger.info(f"Refund Successful for Payment {payment_id}. Refund ID: {refund.get('id')}")
        return f"Refund Processed: {refund.get('id')}"

    except Exception as e:
        logger.error(f"Refund Failed for Payment {payment_id}: {e}")
        # Retry logic can be added here (e.g., self.retry())
        return f"Refund Failed: {e}"