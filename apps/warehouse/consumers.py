import json
from channels.generic.websocket import AsyncWebsocketConsumer


class WMSConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # --- SECURITY FIX START ---
        user = self.scope["user"]
        # Sirf authenticated staff members hi connect kar sakein
        if not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        # --- SECURITY FIX END ---

        self.group_name = "wms_realtime"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Disconnect hone par group se remove karein
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def wms_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))