# apps/orders/receivers.py
import logging
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

# FIXED IMPORTS
from apps.orders.signals import send_order_created, order_refund_requested
from apps.warehouse.signals import item_fulfillment_cancelled 
from apps.payments.signals import payment_succeeded
from apps.delivery.signals import delivery_completed, rider_assigned_to_dispatch

from .models import Order, OrderTimeline

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(payment_succeeded)
def handle_payment_success(sender, order, **kwargs):
    if order.status == "pending":
        order.status = "confirmed"
        order.payment_status = "paid"
        order.save(update_fields=["status", "payment_status"])
        
        OrderTimeline.objects.create(order=order, status="confirmed", notes="Payment successful.")
        
        try:
            wms_items_list = [
                {"sku_id": str(item.sku.id), "qty": item.quantity}
                for item in order.items.all().select_related('sku')
            ]
            
            # USING LOCAL SIGNAL
            send_order_created.send(
                sender=Order,
                order_id=order.id,
                customer_id=order.customer.id if order.customer else None,
                order_items=wms_items_list,
                metadata={
                    "warehouse_id": str(order.warehouse.id) if order.warehouse else None
                }
            )
            logger.info(f"WMS signal sent for confirmed order {order.id}")
        except Exception as e:
            logger.exception(f"Failed to send WMS signal for order {order.id}: {e}")


@receiver(delivery_completed)
def handle_delivery_success(sender, order, rider_code, **kwargs):
    """
    Delivery complete hone par order status update karo.
    """
    if order.status != "delivered":
        order.status = "delivered"
        order.delivered_at = timezone.now()
        order.save(update_fields=['status', 'delivered_at'])
        
        OrderTimeline.objects.create(
            order=order,
            status="delivered",
            notes=f"Delivered by rider {rider_code}."
        )
        logger.info(f"Order {order.id} marked as delivered.")

@receiver(rider_assigned_to_dispatch)
def handle_rider_assigned(sender, order_id, rider_user_id, **kwargs):
    """
    Jab rider assign ho jaye, toh order status 'dispatched' karo.
    """
    try:
        order = Order.objects.get(id=order_id)
        rider_user = User.objects.get(id=rider_user_id)
        
        if order.status in ["ready", "packed", "confirmed", "picking"]:
            order.status = "dispatched"
            order.rider = rider_user
            order.save(update_fields=['status', 'rider'])
            
            rider_profile = getattr(rider_user, 'rider_profile', None)
            rider_code = rider_profile.rider_code if rider_profile else "Unknown"

            OrderTimeline.objects.create(
                order=order,
                status="dispatched",
                notes=f"Rider {rider_code} assigned."
            )
            logger.info(f"Order {order.id} marked as dispatched.")
    except Exception as e:
        logger.error(f"Error updating Order {order_id} from rider assignment: {e}")


@receiver(item_fulfillment_cancelled)
def handle_warehouse_cancellation(sender, order_id, sku_id, qty, reason, **kwargs):
    """
    Decoupled Logic: 
    1. Warehouse tells "Item Cancelled".
    2. Orders app looks up price.
    3. Orders app tells Payments "Refund this amount".
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # 1. Item ki price pata karo (Order ke context mein)
        order_item = order.items.filter(sku__id=sku_id).first()
        
        if not order_item:
            logger.error(f"Item SKU {sku_id} not found in Order {order_id} during cancellation.")
            return

        # 2. Refund Amount Calculate karo
        refund_amount = order_item.unit_price * qty
        
        # 3. Order Timeline Update karo
        OrderTimeline.objects.create(
            order=order,
            status=order.status, 
            notes=f"Item Cancelled by Warehouse: {qty} x {order_item.sku_name_snapshot}. Reason: {reason}"
        )

        # 4. Payments App ko signal bhejo
        if order.payment_status == 'paid':
            order_refund_requested.send(
                sender=Order,
                order_id=order.id,
                amount=refund_amount,
                reason=f"Warehouse Cancellation: {reason}"
            )
            logger.info(f"Triggered refund of {refund_amount} for Order {order.id} via signal.")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found during warehouse cancellation signal.")