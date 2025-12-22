import json
from channels.generic.websocket import AsyncWebsocketConsumer

class WMSConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        
        # Security: Only Staff/Admins/Warehouse Managers
        if not user.is_authenticated or not (user.is_staff or user.role == 'MANAGER'):
            await self.close()
            return

        # Granular subscription based on Warehouse ID logic could go here
        # For now, subscribing to global
        self.room_group_name = "wms_global"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from room group
    async def wms_message(self, event):
        payload = event['payload']
        await self.send(text_data=json.dumps(payload))