from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def broadcast_delivery_update(task, event_type):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    # Payload for Customer Tracking
    payload = {
        "type": "delivery_update", # Handled by Consumer
        "status": task.status,
        "event": event_type,
        "rider_lat": task.rider.current_location.y if task.rider and task.rider.current_location else None,
        "rider_lng": task.rider.current_location.x if task.rider and task.rider.current_location else None,
    }

    # Push to Order Group (Customer)
    async_to_sync(channel_layer.group_send)(
        f"order_{task.order.id}",
        {
            "type": "delivery_event",
            "data": payload
        }
    )