# apps/delivery/receivers.py
import logging

from django.dispatch import receiver

from apps.warehouse.signals import dispatch_ready_for_delivery
from .tasks import create_delivery_task_from_signal

logger = logging.getLogger(__name__)


@receiver(dispatch_ready_for_delivery)
def handle_dispatch_ready_signal(
    sender,
    dispatch_id,
    order_id,
    warehouse_id,
    pickup_otp,
    **kwargs,
):
    """
    WMS se signal sunta hai aur DeliveryTask create + rider assign karwata hai.
    """
    logger.info(
        "Received dispatch_ready_for_delivery signal for Dispatch ID: %s",
        dispatch_id,
    )

    create_delivery_task_from_signal.delay(
        dispatch_id=str(dispatch_id),
        order_id=str(order_id),
        warehouse_id=str(warehouse_id),
        pickup_otp=pickup_otp,
    )
