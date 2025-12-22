# apps/payments/services.py

import logging
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.orders.services import OrderService
from .models import PaymentIntent, Payment, Refund, WebhookLog

logger = logging.getLogger(__name__)


class PaymentService:

    # ---------- INTENT ----------

    @staticmethod
    def create_intent(user, order_id, method: str):
        from apps.orders.models import Order

        order = Order.objects.get(id=order_id, user=user)

        if order.status != order.Status.CREATED:
            raise ValidationError("Order not eligible for payment")

        # Gateway client creation omitted for brevity
        gateway_order_id = f"rzp_{order.order_id}"

        return PaymentIntent.objects.create(
            order=order,
            gateway="razorpay",
            amount=int(order.total_amount * 100),
            currency="INR",
            gateway_order_id=gateway_order_id,
        )

    # ---------- WEBHOOK ----------

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str) -> bool:
        """
        FAIL-CLOSED: if secret missing or invalid, reject.
        """
        secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        if not secret:
            logger.critical("RAZORPAY_WEBHOOK_SECRET missing — rejecting webhook")
            return False

        try:
            client = PaymentService._get_gateway_client()
            client.utility.verify_webhook_signature(body, signature, secret)
            return True
        except Exception:
            return False

    @staticmethod
    @transaction.atomic
    def process_webhook(payload: dict):
        event_id = payload.get("event_id")
        if not event_id:
            raise ValidationError("Missing event_id")

        if WebhookLog.objects.filter(event_id=event_id).exists():
            return  # idempotent

        data = payload.get("payload", {})
        payment_entity = data.get("payment", {}).get("entity", {})

        order_id = payment_entity.get("notes", {}).get("order_id")
        gateway_payment_id = payment_entity.get("id")

        intent = PaymentIntent.objects.select_for_update().get(
            gateway_order_id=payment_entity.get("order_id")
        )

        payment = Payment.objects.create(
            order=intent.order,
            intent=intent,
            gateway_payment_id=gateway_payment_id,
            status=Payment.Status.SUCCESS,
            raw_payload=payload,
        )

        # Confirm order payment
        OrderService.confirm_payment(
            order_id=str(intent.order.id),
            payment_id=gateway_payment_id,
        )

        WebhookLog.objects.create(event_id=event_id)
        return payment

    # ---------- REFUNDS ----------

    @staticmethod
    @transaction.atomic
    def initiate_refund(payment_id: str, amount: int, reason: str):
        payment = Payment.objects.select_for_update().get(id=payment_id)

        refund = Refund.objects.create(
            payment=payment,
            amount=amount,
            status=Refund.Status.INITIATED,
            reason=reason,
        )

        try:
            client = PaymentService._get_gateway_client()
            response = client.payment.refund(
                payment.gateway_payment_id,
                {"amount": amount},
            )

            refund.gateway_refund_id = response.get("id")
            refund.status = Refund.Status.SUCCESS
            refund.save(update_fields=["gateway_refund_id", "status"])
        except Exception as e:
            refund.status = Refund.Status.FAILED
            refund.save(update_fields=["status"])
            logger.exception("Refund failed")
            raise

        return refund

    # ---------- INTERNAL ----------

    @staticmethod
    def _get_gateway_client():
        # return Razorpay client (omitted)
        raise NotImplementedError
