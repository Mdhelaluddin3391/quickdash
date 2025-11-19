# apps/delivery/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.gis.geos import Point
from asgiref.sync import sync_to_async
from .models import Delivery
from apps.accounts.models import RiderProfile

class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # URL se order_id nikalo: /ws/track/<order_id>/
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'order_{self.order_id}'

        # Is group (room) mein join ho jao
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # --- Rider Location Update Receive Karna ---
    async def receive(self, text_data):
        """
        Jab Rider App location bhejega:
        {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "rider_id": 5
        }
        """
        data = json.loads(text_data)
        lat = data.get('latitude')
        lng = data.get('longitude')
        
        # 1. Database mein Location Save karo (Async Wrapper)
        if lat and lng:
            await self.update_rider_location(lat, lng)

        # 2. Customer ko update bhejo (Group Broadcast)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'location_update', # Neeche wala function call hoga
                'latitude': lat,
                'longitude': lng
            }
        )

    # --- Customer ko Update Bhejna ---
    async def location_update(self, event):
        # Web browser ko JSON bhejo
        await self.send(text_data=json.dumps({
            'latitude': event['latitude'],
            'longitude': event['longitude']
        }))

    @sync_to_async
    def update_rider_location(self, lat, lng):
        """
        Rider ki location DB mein update karein taaki history rahe.
        """
        user = self.scope["user"]
        if hasattr(user, 'rider_profile'):
            profile = user.rider_profile
            profile.current_location = Point(float(lng), float(lat))
            profile.save()