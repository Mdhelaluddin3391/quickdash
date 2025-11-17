# apps/orders/signals.py
import logging
from django.dispatch import receiver
from django.utils import timezone
from apps.payments.signals import payment_succeeded
from apps.delivery.signals import delivery_completed
from apps.warehouse.signals import send_order_created
from .models import Order, OrderTimeline

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