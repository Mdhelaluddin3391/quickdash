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


def verify_payment_signature(order_id: str, gateway_order_id: str, gateway_payment_id: str, gateway_signature: str) -> bool:
    """
    Verify signature coming from Razorpay checkout.
    """
    if not razorpay_client:
        raise RuntimeError("Razorpay client is not configured.")

    params_dict = {
        "razorpay_order_id": gateway_order_id,
        "razorpay_payment_id": gateway_payment_id,
        "razorpay_signature": gateway_signature,
    }
    try:
        razorpay_client.utility.verify_payment_signature(params_dict)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def initiate_refund(refund: Refund) -> tuple[bool, str | dict]:
    """
    Call Razorpay refund API for a given Refund record.
    """
    payment = refund.payment
    if payment.payment_method != Payment.PaymentMethod.RAZORPAY:
        return False, "Only Razorpay payments support online refunds."

    if not payment.transaction_id:
        return False, "No transaction ID found on Payment."

    if not razorpay_client:
        return False, "Razorpay client not configured."

    try:
        rp_refund = razorpay_client.payment.refund(
            payment.transaction_id,
            {
                "amount": int(refund.amount * 100),
                "speed": "normal",
            },
        )
        return True, rp_refund
    except Exception as e:
        logger.exception("Error initiating refund for payment %s: %s", payment.id, e)
        return False, str(e)
