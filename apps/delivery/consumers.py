# apps/delivery/consumers.py

import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.orders.models import Order


class OrderTrackingConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        is_allowed = await self._has_access(user)
        if not is_allowed:
            await self.close(code=4003)
            return

        self.group_name = f"order_{self.order_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def delivery_event(self, event):
        await self.send_json(event["data"])

    async def _has_access(self, user):
        return await Order.objects.filter(
            id=self.order_id,
            user=user,
        ).aexists()
