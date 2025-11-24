import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.gis.geos import Point
from django.utils import timezone

from .models import DeliveryTask


class RiderLocationConsumer(AsyncWebsocketConsumer):
    """
    Rider app -> sends live location.
    URL: ws://domain/ws/rider/location/
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
        else:
            await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        lat = data.get("lat")
        lng = data.get("lng")

        if lat is None or lng is None:
            return

        await self.update_rider_location(lat, lng)

        active_order_id = await self.get_active_order_id()
        if active_order_id:
            await self.channel_layer.group_send(
                f"order_{active_order_id}",
                {
                    "type": "location_update",
                    "lat": lat,
                    "lng": lng,
                },
            )

    @database_sync_to_async
    def update_rider_location(self, lat, lng):
        try:
            profile = self.user.rider_profile
        except Exception:
            return

        profile.current_location = Point(float(lng), float(lat))
        profile.last_location_update = timezone.now()
        profile.save(update_fields=["current_location", "last_location_update"])

    @database_sync_to_async
    def get_active_order_id(self):
        try:
            task = (
                DeliveryTask.objects.filter(
                    rider__user=self.user,
                    status=DeliveryTask.DeliveryStatus.PICKED_UP,
                )
                .select_related("order")
                .first()
            )
            if not task:
                return None
            return str(task.order.id)
        except Exception:
            return None


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    """
    Customer/frontend order tracker.

    URL: ws://domain/ws/order/track/<order_id>/
    """

    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.group_name = f"order_{self.order_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def location_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "lat": event["lat"],
                    "lng": event["lng"],
                }
            )
        )