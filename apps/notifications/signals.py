from django.dispatch import receiver
from django.db.models.signals import post_save
from apps.orders.models import Order, OrderTimeline
from .tasks import send_order_notification

@receiver(post_save, sender=OrderTimeline)
def order_status_change_notification(sender, instance, created, **kwargs):
    if created:
        order = instance.order
        status = instance.status
        customer = order.customer
        
        if not customer:
            return

        # Simple message mapping
        messages = {
            "confirmed": "Your order is confirmed!",
            "picking": "We are picking your items.",
            "packed": "Your order is packed.",
            "dispatched": "Rider is on the way!",
            "delivered": "Order Delivered. Enjoy!",
            "cancelled": "Order Cancelled.",
        }

        if status in messages:
            send_order_notification.delay(
                customer.id, 
                "Order Update", 
                messages[status]
            )