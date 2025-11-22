# apps/analytics/receivers.py
import logging
from django.dispatch import receiver
from apps.orders.signals import send_order_created
from apps.delivery.signals import delivery_completed

logger = logging.getLogger(__name__)

@receiver(send_order_created)
def track_order_creation(sender, order_id, **kwargs):
    """
    Log or update real-time dashboard when an order is created.
    For now, we just log it.
    """
    logger.info(f"[Analytics] Order {order_id} created. Ready for aggregation.")

@receiver(delivery_completed)
def track_delivery_completion(sender, order, rider_code, **kwargs):
    """
    Log delivery for analytics.
    """
    logger.info(f"[Analytics] Order {order.id} delivered by {rider_code}.")