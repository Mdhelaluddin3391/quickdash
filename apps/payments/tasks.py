# apps/payments/tasks.py
import logging
from celery import shared_task
from django.db import transaction

from .models import Payment, Refund
from .services import initiate_refund

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_order_refund_task(self, order_id: str, amount: str, reason: str | None = None):
    """
    Background task to process a refund for an order.

    - Finds last successful online Payment for the order.
    - Creates Refund row.
    - Calls Razorpay via initiate_refund().
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("Refund task: Order %s not found.", order_id)
        return

    # latest successful Razorpay payment
    payment = (
        Payment.objects.filter(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESSFUL,
        )
        .order_by("-created_at")
        .first()
    )

    if not payment:
        logger.error(
            "Refund task: No successful Razorpay payment found for order %s",
            order_id,
        )
        return

    try:
        amount_dec = payment.amount if amount is None else type(payment.amount)(amount)
    except Exception:
        amount_dec = payment.amount

    with transaction.atomic():
        refund = Refund.objects.create(
            payment=payment,
            order=order,
            amount=amount_dec,
            reason=reason or "",
            status=Refund.RefundStatus.PENDING,
        )

        payment.status = Payment.PaymentStatus.REFUND_INITIATED
        payment.save(update_fields=["status"])

    success, result = initiate_refund(refund)

    if success:
        logger.info("Refund successful for payment %s", payment.id)
        with transaction.atomic():
            refund.status = Refund.RefundStatus.SUCCESS
            refund.gateway_refund_id = result.get("id", "")
            refund.gateway_response = result
            refund.save(
                update_fields=[
                    "status",
                    "gateway_refund_id",
                    "gateway_response",
                    "updated_at",
                ]
            )
            payment.status = Payment.PaymentStatus.REFUNDED
            payment.save(update_fields=["status"])
    else:
        logger.error(
            "Refund failed for payment %s: %s",
            payment.id,
            result,
        )
        with transaction.atomic():
            refund.status = Refund.RefundStatus.FAILED
            refund.gateway_response = {
                "error": str(result),
            }
            refund.save(
                update_fields=["status", "gateway_response", "updated_at"]
            )
            payment.status = Payment.PaymentStatus.FAILED
            payment.save(update_fields=["status"])
