import logging
from django.dispatch import receiver
from apps.delivery.signals import rider_assigned_to_dispatch
from .models import DispatchRecord
from .signals import send_order_created
from .tasks import orchestrate_order_fulfilment_from_order_payload
from apps.orders.signals import send_order_created  # <--- FIXED IMPORT
from apps.orders.signals import send_order_created

logger = logging.getLogger(__name__)

@receiver(send_order_created)
def handle_order_created(sender, order_id, order_items, metadata=None, **kwargs):
    payload = {
        "order_id": str(order_id),
        "items": order_items,
        "metadata": metadata or {},
    }
    logger.info("send_order_created -> enqueue orchestrator: %s", payload)
    orchestrate_order_fulfilment_from_order_payload.delay(payload)

@receiver(rider_assigned_to_dispatch)
def handle_rider_assigned_signal(sender, dispatch_id, rider_profile_id, **kwargs):
    """
    Delivery app se signal sunta hai aur DispatchRecord ko update karta hai.
    """
    try:
        dispatch = DispatchRecord.objects.get(id=dispatch_id)
        if dispatch.status == "ready":
            dispatch.status = "assigned"
            dispatch.rider_id = str(rider_profile_id)
            dispatch.save(update_fields=['status', 'rider_id'])
            logger.info(f"DispatchRecord {dispatch_id} updated to 'assigned' by delivery app signal.")
        else:
            logger.warning(f"Received rider assignment for Dispatch {dispatch_id}, but status was already {dispatch.status}.")
    except DispatchRecord.DoesNotExist:
        logger.error(f"Received rider assignment for non-existent DispatchRecord {dispatch_id}.")
    except Exception as e:
        logger.exception(f"Error updating DispatchRecord {dispatch_id} from signal: {e}")