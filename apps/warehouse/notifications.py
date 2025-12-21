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


def notify_packer_new_task(packing_task):
    """
    Triggered when a Picking Task is completed and Packing Task is ready.
    """
    try:
        warehouse = packing_task.picking_task.warehouse
        logger.info(f"📢 Notification: New Packing Task #{packing_task.id} at {warehouse.name}")
        # Integration point for FCM or WebSocket (Channels)
        # send_websocket_message(group=f"warehouse_{warehouse.id}", type="new_task", data={...})
    except Exception as e:
        logger.error(f"Failed to notify packer: {e}")


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
    Triggered when packing is done and order is ready for pickup.
    """
    try:
        logger.info(f"📢 Notification: Dispatch Ready for Order #{dispatch_record.order_id}. OTP: {dispatch_record.pickup_otp}")
        # Send SMS to Rider or Customer
    except Exception as e:
        logger.error(f"Failed to notify dispatch: {e}")