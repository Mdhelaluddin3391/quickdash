# apps/warehouse/signals.py
from django.dispatch import receiver, Signal
import logging

# FIX: Yahaan se task import ko HATA diya gaya hai
# from .tasks import orchestrate_order_fulfilment_from_order_payload 

from apps.delivery.signals import rider_assigned_to_dispatch
from .models import DispatchRecord # Model ko update karne ke liye

logger = logging.getLogger(__name__)

# --- Signal (payments -> wms) ---
send_order_created = Signal()

# --- Signal (wms -> delivery) ---
dispatch_ready_for_delivery = Signal()


@receiver(send_order_created)
def handle_order_created(sender, order_id, order_items, metadata=None, **kwargs):
    
    # --- FIX: Import ko function ke ANDAR move kar diya gaya hai ---
    # Isse circular import fix ho jaata hai
    from .tasks import orchestrate_order_fulfilment_from_order_payload
    
    payload = {
        "order_id": str(order_id),
        "items": order_items,
        "metadata": metadata or {},
    }
    logger.info("send_order_created -> enqueue orchestrator: %s", payload)
    orchestrate_order_fulfilment_from_order_payload.delay(payload)


# --- Receiver (delivery -> wms) ---
@receiver(rider_assigned_to_dispatch)
def handle_rider_assigned_signal(sender, dispatch_id, rider_profile_id, **kwargs):
    """
    Delivery app se signal sunta hai aur DispatchRecord ko update karta hai.
    """
    try:
        dispatch = DispatchRecord.objects.get(id=dispatch_id)
        if dispatch.status == "ready":
            dispatch.status = "assigned"
            dispatch.rider_id = str(rider_profile_id) # Hum yahaan sirf ID save kar rahe hain
            dispatch.save(update_fields=['status', 'rider_id'])
            logger.info(f"DispatchRecord {dispatch_id} updated to 'assigned' by delivery app signal.")
        else:
            logger.warning(f"Received rider assignment for Dispatch {dispatch_id}, but status was already {dispatch.status}.")
    except DispatchRecord.DoesNotExist:
        logger.error(f"Received rider assignment signal for non-existent DispatchRecord {dispatch_id}.")
    except Exception as e:
        logger.error(f"Error updating DispatchRecord {dispatch_id} from signal: {e}")