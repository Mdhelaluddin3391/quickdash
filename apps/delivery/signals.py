# apps/delivery/signals.py

import logging
from django.dispatch import receiver, Signal
from apps.warehouse.signals import dispatch_ready_for_delivery
from .tasks import create_delivery_task_from_signal

logger = logging.getLogger(__name__)

# --- FIX: Naya Signal (delivery -> wms) ---
# Yeh wms ko batayega ki rider assign ho gaya hai
rider_assigned_to_dispatch = Signal()

# --- FIX: Naya Signal (delivery -> orders) ---
# Yeh orders ko batayega ki delivery poori ho gayi hai
delivery_completed = Signal()


@receiver(dispatch_ready_for_delivery)
def handle_dispatch_ready_signal(sender, dispatch_id, order_id, warehouse_id, pickup_otp, **kwargs):
    """
    WMS se signal sunta hai.
    """
    logger.info(f"Received dispatch_ready_for_delivery signal for Dispatch ID: {dispatch_id}")
    
    create_delivery_task_from_signal.delay(
        dispatch_id=str(dispatch_id),
        order_id=str(order_id),
        warehouse_id=str(warehouse_id),
        pickup_otp=pickup_otp
    )