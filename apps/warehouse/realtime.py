from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging

logger = logging.getLogger(__name__)

def broadcast_wms_event(event_data: dict):
    """
    Broadcasts operational events to warehouse dashboard.
    Event structure: { "type": "...", "warehouse_id": 1, ... }
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    # Broadcast to a general group or warehouse-specific group
    group_name = "wms_global"
    if "warehouse_id" in event_data:
        group_name = f"wms_{event_data['warehouse_id']}"

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "wms.message",  # Matches consumer method
                "payload": event_data
            }
        )
    except Exception as e:
        logger.error(f"Failed to broadcast WMS event: {e}")