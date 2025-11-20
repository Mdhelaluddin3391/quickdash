# apps/warehouse/notifications.py
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

def _send_ws_message(group_name, event_type, payload):
    """
    Helper function to broadcast message to a WebSocket group.
    """
    channel_layer = get_channel_layer()
    
    if not channel_layer:
        logger.error("Channel Layer not found! Notification skipped.")
        return

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "wms_event",  # Yeh 'consumers.py' mein method name se match hona chahiye
                "data": {
                    "event": event_type,
                    **payload
                }
            }
        )
        logger.info(f"WebSocket Sent: {event_type} -> {group_name}")
    except Exception as e:
        logger.exception(f"Failed to send WebSocket message: {e}")


def notify_picker_new_task(picking_task):
    """
    Picker ko batayein ki naya task aaya hai.
    """
    payload = {
        "task_id": str(picking_task.id),
        "order_id": picking_task.order_id,
        "warehouse_id": str(picking_task.warehouse_id),
        "items_count": picking_task.items.count(),
        "status": picking_task.status,
    }
    # Real-time message bhejein
    _send_ws_message("wms_realtime", "new_pick_task", payload)


def notify_packer_new_task(packing_task):
    """
    Packer ko batayein ki picking complete ho gayi, ab pack karna hai.
    """
    payload = {
        "packing_task_id": str(packing_task.id),
        "order_id": packing_task.picking_task.order_id,
        "warehouse_id": str(packing_task.picking_task.warehouse_id),
        "status": "pending",
    }
    _send_ws_message("wms_realtime", "new_pack_task", payload)


def notify_dispatch_ready(dispatch_record):
    """
    Dispatch area (Rider/Coordinator) ko batayein ki packet ready hai.
    """
    payload = {
        "dispatch_id": str(dispatch_record.id),
        "order_id": dispatch_record.order_id,
        "warehouse_id": str(dispatch_record.warehouse_id),
        "pickup_otp": dispatch_record.pickup_otp,
        "status": "ready",
    }
    _send_ws_message("wms_realtime", "dispatch_ready", payload)