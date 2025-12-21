# apps/payments/services.py
import logging
from decimal import Decimal

import razorpay
from django.conf import settings

from .models import Payment, Refund

logger = logging.getLogger(__name__)

# Single shared client
try:
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        logger.info("Razorpay client initialized in payments.services")
    else:
        razorpay_client = None
        logger.error("Razorpay keys missing in settings.")
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay client: {e}")


def create_razorpay_order(order, amount: Decimal, currency: str = "INR") -> str:
    """
    Create a Razorpay order ID for a given amount.
    Amount must be in rupees (Decimal); we convert to paise.
    """
    if not razorpay_client:
        raise RuntimeError("Razorpay client is not configured.")

    data = {
        "amount": int(amount * 100),
        "currency": currency,
        "receipt": str(order.id),
        "payment_capture": 1,
        "notes": {
            "order_id": str(order.id),
            "customer_phone": getattr(order.customer, "phone", ""),
        },
    }
    rp_order = razorpay_client.order.create(data=data)
    return rp_order["id"]


def verify_payment_signature(gateway_order_id: str, gateway_payment_id: str, gateway_signature: str) -> bool:
    """
    Strict signature verification using Razorpay SDK.
    """
    if not razorpay_client:
        raise RuntimeError("Razorpay client is not configured.")

    try:
        # Standard Razorpay HMAC verification
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': gateway_order_id,
            'razorpay_payment_id': gateway_payment_id,
            'razorpay_signature': gateway_signature
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.warning(f"Signature Verification Failed for Order: {gateway_order_id}")
        return False


# apps/payments/services.py

def initiate_refund(refund_obj: Refund) -> tuple[bool, str | dict]:
    """
    Call Razorpay refund API for a given Refund record.
    Includes strict double-refund protection.
    """
    from django.db import transaction
    from django.db.models import Sum

    try:
        with transaction.atomic():
            # 1. Lock the Payment Record to serialize refund attempts
            payment = Payment.objects.select_for_update().get(id=refund_obj.payment.id)
            
            if payment.payment_method != Payment.PaymentMethod.RAZORPAY:
                return False, "Only Razorpay payments support online refunds."

            if not payment.transaction_id:
                return False, "No transaction ID found on Payment."

            if not razorpay_client:
                return False, "Razorpay client not configured."

            # 2. Financial Integrity Check
            # Calculate total ALREADY refunded (excluding this new attempt if it's already saved but not processed)
            existing_refunds = Refund.objects.filter(
                payment=payment, 
                status='COMPLETED'
            ).exclude(id=refund_obj.id).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            if (existing_refunds + refund_obj.amount) > payment.amount:
                return False, f"Refund amount exceeds refundable balance. Refunded: {existing_refunds}, Max: {payment.amount}"

            # 3. Execute Gateway Call
            try:
                rp_refund = razorpay_client.payment.refund(
                    payment.transaction_id,
                    {
                        "amount": int(refund_obj.amount * 100), # Convert to paise
                        "speed": "normal",
                        "notes": {"refund_id": str(refund_obj.id)}
                    },
                )
                
                # 4. Update Status on Success
                refund_obj.gateway_refund_id = rp_refund.get('id')
                refund_obj.status = 'COMPLETED'
                refund_obj.save()
                
                return True, rp_refund
                
            except razorpay.errors.RazorpayError as e:
                logger.error(f"Razorpay Refund Error: {e}")
                refund_obj.status = 'FAILED'
                refund_obj.save()
                return False, str(e)

    except Exception as e:
        logger.exception("Error initiating refund for payment %s: %s", refund_obj.payment.id, e)
        return False, str(e)