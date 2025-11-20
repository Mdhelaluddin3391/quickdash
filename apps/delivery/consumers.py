import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.gis.geos import Point
from channels.db import database_sync_to_async
from .models import DeliveryTask

class RiderLocationConsumer(AsyncWebsocketConsumer):
    """
    Rider App isse connect karega aur har 5-10 second mein location bhejega.
    URL: ws://domain/ws/rider/location/
    """
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
        else:
            await self.accept()

    async def receive(self, text_data):
        """
        Rider se location aayi -> DB mein save karo -> Order group mein broadcast karo.
        Data format: {"lat": 12.9716, "lng": 77.5946}
        """
        data = json.loads(text_data)
        lat = data.get('lat')
        lng = data.get('lng')

        if lat and lng:
            # 1. Rider ki location DB mein update karo
            await self.update_rider_location(lat, lng)
            
            # 2. Agar Rider kisi active delivery par hai, toh Customer ko update bhejo
            active_order_id = await self.get_active_order_id()
            if active_order_id:
                # Order specific room mein message bhejo
                await self.channel_layer.group_send(
                    f"order_{active_order_id}",
                    {
                        "type": "location_update",
                        "lat": lat,
                        "lng": lng
                    }
                )

    @database_sync_to_async
    def update_rider_location(self, lat, lng):
        try:
            profile = self.user.rider_profile
            profile.current_location = Point(float(lng), float(lat)) # GeoDjango Point (Lng, Lat)
            profile.save()
        except:
            pass

    @database_sync_to_async
    def get_active_order_id(self):
        # Check karo agar rider ke paas koi 'PICKED_UP' task hai
        try:
            task = DeliveryTask.objects.filter(
                rider__user=self.user, 
                status='PICKED_UP'
            ).first()
            return str(task.order.id) if task else None
        except:
            return None


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    """
    Customer/Frontend isse connect karega order track karne ke liye.
    URL: ws://domain/ws/order/track/<order_id>/
    """
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.group_name = f"order_{self.order_id}"

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def location_update(self, event):
        # RiderLocationConsumer se jo data aaya, use Customer ko bhejo
        await self.send(text_data=json.dumps({
            "lat": event["lat"],
            "lng": event["lng"]
        }))