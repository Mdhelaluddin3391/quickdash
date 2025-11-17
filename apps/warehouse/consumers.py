import json
from channels.generic.websocket import AsyncWebsocketConsumer


class WMSConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "wms_realtime"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Client → server messages (optional, abhi ignore)
        pass

    async def wms_event(self, event):
        """
        Called by group_send(type='wms_event', data={...})
        """
        await self.send(text_data=json.dumps(event["data"]))
