import logging
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

# Imports from other apps (Signals ONLY)
from apps.payments.signals import payment_succeeded
from apps.delivery.signals import delivery_completed, rider_assigned_to_dispatch
from apps.warehouse.signals import send_order_created

# Local Models
from .models import Order, OrderTimeline

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(payment_succeeded)
def handle_payment_success(sender, order, **kwargs):
    """
    Payment success hone par order confirm karo aur WMS ko signal bhejo.
    """
    if order.status == "pending":
        order.status = "confirmed"
        order.payment_status = "paid"
        order.save(update_fields=["status", "payment_status"])
        
        OrderTimeline.objects.create(
            order=order,
            status="confirmed",
            notes="Payment successful."
        )
        
        # Ab WMS ko batao ki order aa gaya hai
        try:
            wms_items_list = [
                {"sku_id": str(item.sku.id), "qty": item.quantity}
                for item in order.items.all()
            ]
            
            # Note: 'send_order_created' signal WMS app mein defined hai
            send_order_created.send(
                sender=Order,
                order_id=order.id,
                order_items=wms_items_list,
                metadata={
                    "warehouse_id": str(order.warehouse.id),
                    "customer_id": str(order.customer.id)
                }
            )
            logger.info(f"WMS signal sent for confirmed order {order.id}")
        except Exception as e:
            logger.error(f"Failed to send WMS signal for order {order.id}: {e}")

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