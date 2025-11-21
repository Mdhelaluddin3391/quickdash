import logging
import random

from django.db import transaction
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.signals import payment_succeeded as payments_payment_succeeded
from apps.warehouse.signals import send_order_created

logger = logging.getLogger(__name__)


def process_successful_payment(order):
    """
    Centralized payment confirmation logic for Orders app.
    - Mark order as confirmed/paid
    - Update payment record
    - Create delivery/picking tasks via signals
    - Emit a single `payments.payment_succeeded` signal so other apps can react
    """
    try:
        with transaction.atomic():
            # lock order at caller if needed; here we assume caller provides fresh instance
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])

            payment = order.payments.first()
            if payment:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.save(update_fields=["status"])

            # Inform WMS (warehouse) by sending the pre-defined WMS signal
            try:
                wms_items_list = [
                    {"sku_id": str(item.sku.id), "qty": item.quantity}
                    for item in order.items.all().select_related('sku')
                ]
                send_order_created.send(
                    sender=order.__class__,
                    order_id=order.id,
                    order_items=wms_items_list,
                    metadata={
                        "warehouse_id": str(order.warehouse.id) if order.warehouse else None,
                        "customer_id": str(order.customer.id) if order.customer else None,
                    }
                )
            except Exception:
                logger.exception("Failed to send WMS signal for order %s", order.id)

            # Emit canonical payments signal so receivers across apps can act
            try:
                payments_payment_succeeded.send(sender=order.__class__, order=order)
            except Exception:
                logger.exception("Failed to emit payments.payment_succeeded for order %s", order.id)

            return True, "Success"

    except Exception as e:
        logger.exception("Payment processing failed for order %s: %s", getattr(order, 'id', 'unknown'), e)
        return False, str(e)


def create_order_from_cart(user, warehouse_id, delivery_address_json, delivery_lat=None, delivery_lng=None, payment_method='RAZORPAY'):
    """
    Create an Order from user's cart.
    - Creates Order and OrderItems (uses bulk_create but populates computed fields)
    - Creates a Payment record if needed and returns order and payment
    """
    from .models import Order, OrderItem
    from apps.cart.models import Cart as CartModel if False else None
    # Local import to avoid circular imports; use app models directly
    from apps.orders.models import Cart, CartItem  # type: ignore
    from apps.payments.models import Payment

    try:
        cart = Cart.objects.select_related('customer').prefetch_related('items__sku').get(customer=user)
    except Cart.DoesNotExist:
        return None, None, "Cart not found"

    if not cart.items.exists():
        return None, None, "Cart empty"

    # create order
    order = Order.objects.create(
        customer=user,
        warehouse_id=warehouse_id,
        delivery_address_json=delivery_address_json,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng,
        status='pending',
        payment_status='pending',
    )

    items_to_create = []
    for c_item in cart.items.select_related('sku').all():
        unit_price = getattr(c_item.sku, 'sale_price', 0)
        total_price = unit_price * c_item.quantity
        sku_name_snapshot = getattr(c_item.sku, 'name', '')
        items_to_create.append(
            OrderItem(
                order=order,
                sku=c_item.sku,
                quantity=c_item.quantity,
                unit_price=unit_price,
                total_price=total_price,
                sku_name_snapshot=sku_name_snapshot,
            )
        )

    OrderItem.objects.bulk_create(items_to_create)
    order.recalculate_totals(save=True)

    payment = None
    if payment_method == 'COD':
        payment = Payment.objects.create(order=order, payment_method=Payment.PaymentMethod.COD, amount=order.final_amount)

    # Do not delete cart here; caller may want to control deletion after successful payment
    return order, payment, None


def cancel_order(order, cancelled_by=None, reason=""):
    """
    Cancel an order (customer / system / ops initiated).

    - Guards against invalid states (delivered / already cancelled)
    - Updates Order.status
    - Creates OrderTimeline entry
    - Creates OrderCancellation record (if model present)
    - Emits `order_refund_requested` signal if payment_status == 'paid'
    """
    from .models import OrderTimeline, OrderCancellation  # OrderCancellation model from cancellation.py

    try:
        # 1. Invalid states
        if order.status in ['cancelled', 'delivered']:
            return False, 'Cannot cancel order in its current state.'

        # 2. Mark order as cancelled
        order.status = 'cancelled'
        order.save(update_fields=['status'])

        # 3. Timeline entry
        OrderTimeline.objects.create(
            order=order,
            status='cancelled',
            notes=reason or '',
        )

        # 4. Store cancellation metadata
        # cancelled_by -> expected 'CUSTOMER' / 'SYSTEM' / 'OPS'
        cancelled_by_value = cancelled_by or 'SYSTEM'
        OrderCancellation.objects.create(
            order=order,
            reason_code='GENERIC',
            reason_text=reason or '',
            cancelled_by=cancelled_by_value,
        )

        # 5. If paid, trigger refund flow via signal
        if order.payment_status == 'paid':
            from apps.orders.signals import order_refund_requested
            order_refund_requested.send(
                sender=order.__class__,
                order_id=order.id,
                amount=order.final_amount,
                reason=reason,
            )

        return True, None

    except Exception as e:
        logger.exception(
            'Failed to cancel order %s: %s',
            getattr(order, 'id', 'unknown'),
            e,
        )
        return False, str(e)
