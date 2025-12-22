import razorpay
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from apps.utils.exceptions import BusinessLogicException
from apps.orders.services import OrderService
from .models import PaymentTransaction, RefundRecord, WebhookEvent

logger = logging.getLogger(__name__)

class PaymentService:
    
    @staticmethod
    def _get_client():
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise BusinessLogicException("Payment Gateway not configured.")
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    @staticmethod
    @transaction.atomic
    def create_payment_order(order):
        """
        Initiates a payment session with Razorpay.
        """
        client = PaymentService._get_client()
        amount_paise = int(order.total_amount * 100)
        
        try:
            gateway_order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": str(order.id),
                "notes": {"user_id": str(order.user.id)}
            })
        except Exception as e:
            logger.error(f"Razorpay Create Error: {e}")
            raise BusinessLogicException("Failed to initiate payment gateway.")

        # Create Transaction Record
        PaymentTransaction.objects.create(
            order=order,
            gateway_order_id=gateway_order['id'],
            amount=order.total_amount,
            status=PaymentTransaction.Status.PENDING
        )
        
        return {
            "key": settings.RAZORPAY_KEY_ID,
            "order_id": gateway_order['id'],
            "amount": amount_paise,
            "currency": "INR",
            "name": "QuickDash",
            "description": f"Order #{order.id}"
        }

    @staticmethod
    @transaction.atomic
    def process_payment_success(payload: dict):
        """
        Called after successful verify or webhook.
        """
        ord_id = payload.get('razorpay_order_id')
        pay_id = payload.get('razorpay_payment_id')
        sig = payload.get('razorpay_signature')

        try:
            txn = PaymentTransaction.objects.select_for_update().get(gateway_order_id=ord_id)
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction not found for Gateway Order {ord_id}")
            return False

        if txn.status == PaymentTransaction.Status.SUCCESS:
            return True  # Idempotent

        # Verify Signature (if provided directly from frontend, webhooks use header)
        if sig:
            client = PaymentService._get_client()
            try:
                client.utility.verify_payment_signature(payload)
            except razorpay.errors.SignatureVerificationError:
                txn.status = PaymentTransaction.Status.FAILED
                txn.error_details = {"error": "Signature Verification Failed"}
                txn.save()
                raise BusinessLogicException("Invalid Payment Signature")

        # Update Transaction
        txn.gateway_payment_id = pay_id
        txn.gateway_signature = sig
        txn.status = PaymentTransaction.Status.SUCCESS
        txn.save()

        # Update Order
        OrderService.mark_order_paid(txn.order.id, pay_id)
        return True

    @staticmethod
    def initiate_refund(order):
        """
        Called when an Order is Cancelled.
        """
        try:
            # Find the successful transaction
            txn = order.transactions.filter(status=PaymentTransaction.Status.SUCCESS).first()
            if not txn:
                logger.warning(f"No successful transaction found for Order {order.id} to refund.")
                return

            client = PaymentService._get_client()
            
            # Full Refund
            refund_data = client.payment.refund(txn.gateway_payment_id, {
                "amount": int(txn.amount * 100),
                "speed": "normal"
            })

            RefundRecord.objects.create(
                transaction=txn,
                gateway_refund_id=refund_data['id'],
                amount=txn.amount,
                status=refund_data['status']
            )
            
            txn.status = PaymentTransaction.Status.REFUNDED
            txn.save()
            logger.info(f"Refund processed for Order {order.id}")

        except Exception as e:
            logger.error(f"Refund Failed for Order {order.id}: {e}")
            # In a real system, this should queue a retry task.
            # We will raise it so the caller (Task/View) knows it failed.
            raise BusinessLogicException("Refund failed via Gateway.")

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str):
        client = PaymentService._get_client()
        return client.utility.verify_webhook_signature(
            body.decode('utf-8'), signature, settings.RAZORPAY_WEBHOOK_SECRET
        )