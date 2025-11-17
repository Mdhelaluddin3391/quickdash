# apps/warehouse/signals.py
from django.dispatch import receiver, Signal
import logging

from .tasks import orchestrate_order_fulfilment_from_order_payload

logger = logging.getLogger(__name__)

# Other apps can send this when an order is created.
# Example:
#   from apps.warehouse.signals import send_order_created
#   send_order_created.send(
#       sender=Order,
#       order_id=order.id,
#       order_items=[{"sku_id": item.sku_id, "qty": item.qty}]],
#       metadata={...},
#   )
send_order_created = Signal()


@receiver(send_order_created)
def handle_order_created(sender, order_id, order_items, metadata=None, **kwargs):
    payload = {
        "order_id": str(order_id),
        "items": order_items,
        "metadata": metadata or {},
    }
    logger.info("send_order_created -> enqueue orchestrator: %s", payload)
    orchestrate_order_fulfilment_from_order_payload.delay(payload)
