import logging
from django.db import transaction
from apps.payments.models import Payment
from apps.payments.signals import payment_succeeded as payments_payment_succeeded
from apps.orders.signals import send_order_created # <--- FIXED IMPORT

logger = logging.getLogger(__name__)

def process_successful_payment(order):
    try:
        with transaction.atomic():
            # 1. Update Order Status
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])

            # 2. Update Payment Record
            payment = order.payments.first()
            if payment:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.save(update_fields=["status"])

            # 3. Prepare WMS Payload
            wms_items_list = [
                {"sku_id": str(item.sku.id), "qty": item.quantity}
                for item in order.items.all().select_related('sku')
            ]
            
            # 4. Define the trigger function
            def trigger_wms_signal():
                try:
                    send_order_created.send(
                        sender=order.__class__,
                        order_id=order.id,
                        order_items=wms_items_list,
                        metadata={
                            "warehouse_id": str(order.warehouse.id) if order.warehouse else None,
                            "customer_id": str(order.customer.id) if order.customer else None,
                        }
                    )
                    logger.info(f"WMS signal sent for confirmed order {order.id}")
                except Exception:
                    logger.exception("Failed to send WMS signal")

            # 5. Execute ONLY after commit [FIX]
            transaction.on_commit(trigger_wms_signal)

            # 6. Notify Payments App
            transaction.on_commit(lambda: payments_payment_succeeded.send(sender=order.__class__, order=order))

            return True, "Success"
    except Exception as e:
        logger.exception(f"Payment processing failed: {e}")
        return False, str(e)

# ... (Rest of the file remains unchanged)

def create_order_from_cart(user, warehouse_id, delivery_address_json, delivery_lat=None, delivery_lng=None, payment_method='RAZORPAY'):
    from .models import Order, OrderItem
    # [FIX] Corrected import
    from apps.orders.models import Cart
    from apps.payments.models import Payment

    try:
        cart = Cart.objects.prefetch_related('items__sku').get(customer=user)
    except Cart.DoesNotExist:
        return None, None, "Cart not found"

    if not cart.items.exists():
        return None, None, "Cart empty"

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
    for c_item in cart.items.all():
        unit_price = c_item.sku.sale_price if c_item.sku.sale_price else 0
        items_to_create.append(
            OrderItem(
                order=order,
                sku=c_item.sku,
                quantity=c_item.quantity,
                unit_price=unit_price,
                total_price=unit_price * c_item.quantity,
                sku_name_snapshot=c_item.sku.name,
            )
        )

    OrderItem.objects.bulk_create(items_to_create)
    order.recalculate_totals(save=True)

    payment = None
    if payment_method == 'COD':
        payment = Payment.objects.create(order=order, payment_method=Payment.PaymentMethod.COD, amount=order.final_amount)

    return order, payment, None

def cancel_order(order, cancelled_by=None, reason=""):
    from .models import OrderTimeline, OrderCancellation
    try:
        if order.status in ['cancelled', 'delivered']:
            return False, 'Cannot cancel order in its current state.'

        order.status = 'cancelled'
        order.save(update_fields=['status'])

        OrderTimeline.objects.create(order=order, status='cancelled', notes=reason or '')
        
        OrderCancellation.objects.create(
            order=order,
            reason=reason or '',
            cancelled_by=cancelled_by if isinstance(cancelled_by, str) else 'OPS'
        )

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
        logger.exception(f"Cancel failed: {e}")
        return False, str(e)