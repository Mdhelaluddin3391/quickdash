import razorpay
import logging
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.orders.models import Order
from apps.orders.services import OrderService  # Explicit Cross-App Import
from apps.utils.exceptions import BusinessLogicException
from .models import Payment, PaymentIntent, PaymentStatus, PaymentMethod, WebhookLog

logger = logging.getLogger(__name__)

class PaymentService:
    """
    Service to handle Payment Lifecycle.
    """
    
    @staticmethod
    def get_provider_client():
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    @staticmethod
    def create_intent(user, order_id: str, method: str) -> PaymentIntent:
        """
        Creates a payment order on the Gateway and a PaymentIntent locally.
        """
        try:
            order = Order.objects.get(id=order_id, user=user)
        except Order.DoesNotExist:
            raise ValidationError("Order not found.")

        if order.status != "CREATED": # Assuming 'CREATED' is the pending state
            raise BusinessLogicException(f"Order is not in a payable state: {order.status}")

        if method == PaymentMethod.COD:
            # COD doesn't need a gateway intent, handled directly in OrderService usually,
            # but if we track it here:
            return PaymentService._handle_cod_intent(order, user)

        # 1. Call Gateway
        client = PaymentService.get_provider_client()
        amount_paise = int(order.total_amount * 100)
        
        try:
            provider_order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": str(order.id),
                "payment_capture": 1 
            })
        except Exception as e:
            logger.error(f"Razorpay Order Create Failed: {e}")
            raise BusinessLogicException("Payment Gateway Error")

        # 2. Store Intent
        with transaction.atomic():
            intent = PaymentIntent.objects.create(
                order=order,
                user=user,
                amount=order.total_amount,
                currency="INR",
                gateway_order_id=provider_order['id'],
                status=PaymentStatus.PENDING,
                metadata=provider_order
            )
        
        logger.info(f"Payment Intent Created: {intent.id} for Order: {order.id}")
        return intent

    @staticmethod
    def verify_webhook_signature(body: str, signature: str) -> bool:
        """
        Strict Signature Verification.
        """
        try:
            client = PaymentService.get_provider_client()
            client.utility.verify_webhook_signature(
                body, signature, settings.RAZORPAY_WEBHOOK_SECRET
            )
            return True
        except Exception:
            return False

    @staticmethod
    def process_webhook(event_data: dict):
        """
        Idempotent Webhook Processor.
        Handles: payment.captured, payment.failed
        """
        event_id = event_data.get('account_id', '') + "_" + event_data.get('event', '') + "_" + event_data.get('payload', {}).get('payment', {}).get('entity', {}).get('id', '')
        
        # 1. Idempotency Check
        if WebhookLog.objects.filter(event_id=event_id, is_processed=True).exists():
            logger.info(f"Skipping duplicate webhook event: {event_id}")
            return

        event_type = event_data.get('event')
        payload = event_data.get('payload', {}).get('payment', {}).get('entity', {})
        
        gateway_order_id = payload.get('order_id')
        transaction_id = payload.get('id')
        
        logger.info(f"Processing Webhook: {event_type} for Order: {gateway_order_id}")

        with transaction.atomic():
            # Log receipt
            webhook_log = WebhookLog.objects.create(
                event_id=event_id,
                payload=event_data,
                is_processed=False
            )

            try:
                # Find Intent
                intent = PaymentIntent.objects.select_for_update().get(gateway_order_id=gateway_order_id)
                
                if event_type == 'payment.captured':
                    PaymentService._handle_success(intent, payload, transaction_id)
                elif event_type == 'payment.failed':
                    PaymentService._handle_failure(intent, payload, transaction_id)
                
                # Mark processed
                webhook_log.is_processed = True
                webhook_log.save()

            except PaymentIntent.DoesNotExist:
                logger.error(f"PaymentIntent not found for gateway_order_id: {gateway_order_id}")
                # We do not rollback the log, so we don't retry forever on invalid data
                webhook_log.is_processed = True 
                webhook_log.save()

    @staticmethod
    def _handle_success(intent: PaymentIntent, payload: dict, txn_id: str):
        # 1. Create Payment Record
        payment, created = Payment.objects.get_or_create(
            transaction_id=txn_id,
            defaults={
                'order': intent.order,
                'user': intent.user,
                'payment_intent': intent,
                'amount': Decimal(payload.get('amount', 0)) / 100,
                'currency': payload.get('currency', 'INR'),
                'method': PaymentMethod.RAZORPAY,
                'status': PaymentStatus.SUCCESS,
                'gateway_response': payload
            }
        )
        
        # 2. Update Intent
        intent.status = PaymentStatus.SUCCESS
        intent.save()

        # 3. EXPLICIT Service Call to Orders (No Signals for Logic)
        OrderService.confirm_payment(
            order_id=str(intent.order.id),
            payment_id=txn_id
        )
        logger.info(f"Order {intent.order.id} confirmed via payment {txn_id}")

    @staticmethod
    def _handle_failure(intent: PaymentIntent, payload: dict, txn_id: str):
        Payment.objects.create(
            order=intent.order,
            user=intent.user,
            payment_intent=intent,
            amount=Decimal(payload.get('amount', 0)) / 100,
            currency=payload.get('currency', 'INR'),
            method=PaymentMethod.RAZORPAY,
            transaction_id=txn_id,
            status=PaymentStatus.FAILED,
            gateway_response=payload,
            error_message=payload.get('error_description', 'Payment Failed')
        )
        intent.status = PaymentStatus.FAILED
        intent.save()
        logger.info(f"Payment failed for Order {intent.order.id}")

    @staticmethod
    def _handle_cod_intent(order, user):
        # Simplified placeholder for COD logic
        return PaymentIntent.objects.create(
            order=order,
            user=user,
            amount=order.total_amount,
            gateway_order_id=f"COD-{order.id}", # Internal ID
            status=PaymentStatus.PENDING
        )