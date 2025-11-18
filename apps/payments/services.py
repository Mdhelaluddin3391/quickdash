# apps/payments/services.py
import razorpay
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Refund
from apps.orders.models import Order # Order model is needed here

logger = logging.getLogger(__name__)

def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def process_order_refund(order: Order, amount=None, reason=""):
    """
    Order ka refund process karta hai.
    Agar amount None hai, toh full refund karega.
    """
    # Check karein agar order paid hai tabhi refund karein
    if order.payment_status != 'paid':
        logger.info(f"Order {order.id} is not paid (Status: {order.payment_status}). Skipping refund.")
        return False

    # Successful payment intent dhoondhein
    payment_intent = order.payment_intents.filter(status='paid').last()
    if not payment_intent or not payment_intent.gateway_payment_id:
        logger.error(f"No paid payment intent found for order {order.id}")
        return False

    client = get_razorpay_client()
    refund_amount = amount if amount else order.final_amount
    # Razorpay amount paise mein leta hai
    amount_in_paise = int(refund_amount * 100)

    try:
        with transaction.atomic():
            # 1. Pehle local DB mein Refund record banayein (Pending state)
            refund_record = Refund.objects.create(
                payment=payment_intent,
                order=order,
                amount=refund_amount,
                reason=reason,
                status="pending"
            )

            # 2. Razorpay API call karein
            razorpay_refund = client.payment.refund(
                payment_intent.gateway_payment_id,
                {
                    "amount": amount_in_paise,
                    "speed": "normal",
                    "notes": {
                        "order_id": str(order.id),
                        "reason": reason
                    }
                }
            )

            # 3. Success hone par record update karein
            refund_record.gateway_refund_id = razorpay_refund.get('id')
            refund_record.status = "processed"
            refund_record.processed_at = timezone.now()
            refund_record.save()
            
            # 4. Order ka payment status update karein (agar full refund hai)
            if refund_amount >= order.final_amount:
                order.payment_status = 'refunded'
                order.save(update_fields=['payment_status'])

            logger.info(f"Refund processed successfully for Order {order.id}. ID: {refund_record.gateway_refund_id}")
            return True

    except Exception as e:
        logger.error(f"Refund failed for Order {order.id}: {e}")
        # Fail hone par record update karein
        if 'refund_record' in locals():
            refund_record.status = "failed"
            refund_record.save()
        return False