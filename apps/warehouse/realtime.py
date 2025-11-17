from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_wms_event(event: dict):
    """
    event example:
    {
      "type": "picking_update",
      "task_id": "...",
      "order_id": "...",
      ...
    }
    """
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        "wms_realtime",
        {
            "type": "wms_event",
            "data": event,
        },
    )
