# apps/warehouse/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class WMSConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        
        # [FIX] Allow Staff OR Employees (Pickers/Packers)
        is_employee = getattr(user, "is_employee", False)
        
        if not user.is_authenticated or (not user.is_staff and not is_employee):
            await self.close()
            return

        self.group_name = "wms_realtime"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def wms_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))