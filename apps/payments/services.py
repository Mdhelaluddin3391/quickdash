import hmac
import hashlib
from django.conf import settings
from django.db import transaction
from .models import Transaction, TransactionStatus, PaymentMethod
from apps.orders.services import OrderService
from apps.utils.exceptions import BusinessLogicException

class PaymentService:
    
    @staticmethod
    def initiate_payment(order, method):
        """
        Creates a transaction record and talks to Provider API (Mocked for V2 base).
        """
        if method not in PaymentMethod.values:
            raise BusinessLogicException("Invalid payment method")
            
        txn = Transaction.objects.create(
            order=order,
            user=order.user,
            amount=order.total_amount,
            payment_method=method,
            status=TransactionStatus.INITIATED
        )
        
        # Mocking Provider Interaction
        # In real world: client = razorpay.Client(...)
        # provider_order = client.order.create(...)
        provider_order_id = f"ord_{txn.id}" 
        
        txn.provider_order_id = provider_order_id
        txn.save()
        
        return {
            "transaction_id": txn.id,
            "provider_order_id": provider_order_id,
            "amount": txn.amount,
            "key": settings.PAYMENT_GATEWAY_KEY_ID # from .env
        }

    @staticmethod
    def verify_webhook_signature(payload_body, signature, secret):
        """
        Standard HMAC-SHA256 verification.
        """
        generated_signature = hmac.new(
            bytes(secret, 'utf-8'),
            bytes(payload_body, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(generated_signature, signature)

    @staticmethod
    def process_webhook_success(provider_payment_id, provider_order_id, signature):
        """
        Idempotent handler for success callbacks.
        """
        try:
            txn = Transaction.objects.get(provider_order_id=provider_order_id)
        except Transaction.DoesNotExist:
            raise BusinessLogicException("Transaction not found for this provider order")
            
        # Idempotency Check
        if txn.status == TransactionStatus.SUCCESS:
            return txn
            
        with transaction.atomic():
            # 1. Update Transaction
            txn.status = TransactionStatus.SUCCESS
            txn.provider_payment_id = provider_payment_id
            txn.provider_signature = signature
            txn.save()
            
            # 2. Update Order (Cross-App Call)
            OrderService.mark_order_as_paid(
                order_id=txn.order.id,
                payment_id=provider_payment_id
            )
            
        return txn

from decimal import Decimal
from apps.orders.models import Order, OrderItem
from django.db import transaction

class RefundService:
    @staticmethod
    def calculate_refund_amount(order_item: OrderItem) -> Decimal:
        """
        Calculates the exact refund amount, accounting for:
        1. Item Price
        2. Proportional Discount (Coupon split across items)
        3. Tax adjustments (if applicable)
        """
        order = order_item.order
        
        # 1. Base amount paid for this line item
        line_total = order_item.price_at_booking * order_item.quantity
        
        # 2. If no discount exists, return full amount
        if order.discount_amount <= 0:
            return line_total
            
        # 3. Calculate this item's weight in the total order value (before discount)
        # Avoid division by zero
        if order.total_amount_gross == 0:
            return Decimal('0.00')
            
        item_weight = line_total / order.total_amount_gross
        
        # 4. Calculate share of discount
        item_discount_share = order.discount_amount * item_weight
        
        # 5. Final Refundable Amount
        refundable_amount = line_total - item_discount_share
        
        return round(refundable_amount, 2)

    @staticmethod
    @transaction.atomic
    def process_item_refund(order_item_id):
        item = OrderItem.objects.select_for_update().get(id=order_item_id)
        
        if item.status == 'REFUNDED':
            raise ValueError("Item already refunded")
            
        refund_amount = RefundService.calculate_refund_amount(item)
        
        # ... Trigger Payment Gateway Refund (Razorpay/Stripe) ...
        # payment_gateway.refund(order.payment_id, amount=refund_amount)
        
        item.status = 'REFUNDED'
        item.refunded_amount = refund_amount
        item.save()
        
        return refund_amount