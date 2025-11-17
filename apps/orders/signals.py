# apps/orders/signals.py
import logging
from django.dispatch import receiver
from django.utils import timezone
from apps.payments.signals import payment_succeeded
# FIX: 'rider_assigned_to_dispatch' ko import kiya
from apps.delivery.signals import delivery_completed, rider_assigned_to_dispatch
from apps.warehouse.signals import send_order_created
from .models import Order, OrderTimeline
# FIX: User model ko import karne ke liye imports add kiye
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(payment_succeeded)
def handle_payment_success(sender, order, **kwargs):
    """
    Jab payment app se signal aaye, tab order ko update karo.
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
        
        # Ab 'orders' app WMS ko order process karne ke liye signal bhejega
        # (Yeh logic 'payments' app se yahaan move ho gaya hai)
        try:
            wms_items_list = [
                {"sku_id": str(item.sku_id), "qty": item.quantity}
                for item in order.items.all()
            ]
            
            send_order_created.send(
                sender=Order,
                order_id=order.id,
                order_items=wms_items_list,
                metadata={
                    "warehouse_id": str(order.warehouse_id),
                    "customer_id": str(order.customer_id)
                }
            )
            logger.info(f"WMS signal sent for confirmed order {order.id}")
        except Exception as e:
            logger.error(f"Failed to send WMS signal for order {order.id}: {e}")

@receiver(delivery_completed)
def handle_delivery_success(sender, order, rider_code, **kwargs):
    """
    Jab delivery app se signal aaye, tab order ko 'delivered' mark karo.
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

# --- FIX: YEH NAYA RECEIVER ADD KIYA GAYA HAI ---
@receiver(rider_assigned_to_dispatch)
def handle_rider_assigned(sender, order_id, rider_user_id, **kwargs):
    """
    Jab delivery app se signal aaye ki rider assign ho gaya hai,
    tab order ko 'dispatched' mark karo.
    """
    try:
        order = Order.objects.get(id=order_id)
        rider_user = User.objects.get(id=rider_user_id)
        
        # Check karein ki order pehle se hi delivered ya cancelled na ho
        if order.status in ["ready", "packed", "confirmed", "picking"]:
            order.status = "dispatched"
            order.rider = rider_user
            order.save(update_fields=['status', 'rider'])
            
            OrderTimeline.objects.create(
                order=order,
                status="dispatched",
                # Rider code lene ke liye profile access karna
                notes=f"Rider {getattr(rider_user, 'rider_profile', {}).rider_code} assigned."
            )
            logger.info(f"Order {order.id} marked as dispatched.")
        else:
            logger.warning(f"Order {order.id} received rider assignment but was in status {order.status}.")
            
    except Order.DoesNotExist:
        logger.error(f"Received rider assignment for non-existent Order {order_id}.")
    except User.DoesNotExist:
        logger.error(f"Received rider assignment with non-existent User {rider_user_id}.")
    except Exception as e:
        logger.error(f"Error updating Order {order_id} from rider assignment signal: {e}")