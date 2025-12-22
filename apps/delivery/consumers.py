# apps/delivery/consumers.py

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.orders.models import Order
from apps.delivery.models import DeliveryTask


class OrderTrackingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        allowed = await self._has_access(user)
        if not allowed:
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
        # Customer access
        if await Order.objects.filter(id=self.order_id, user=user).aexists():
            return True

        # Assigned rider access
        return await DeliveryTask.objects.filter(
            order_id=self.order_id,
            rider__user=user,
        ).aexists()
