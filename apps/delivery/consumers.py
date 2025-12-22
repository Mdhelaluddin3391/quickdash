import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class DeliveryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group_name = f"delivery_{self.job_id}"
        
        # Auth Check: Ensure user is related to this job (Customer or Rider)
        # For MVP, we allow connection if authenticated. 
        # Prod: Check DeliveryJob.objects.get(id=job_id).user == self.scope['user']
        
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from WebSocket (e.g., Rider Location Update)
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'location_update':
            # Broadcast to customer
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'delivery_location',
                    'lat': data['lat'],
                    'lng': data['lng']
                }
            )

    # Handlers for Group Messages
    async def delivery_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status'],
            'data': event['data']
        }))

    async def delivery_location(self, event):
        await self.send(text_data=json.dumps({
            'type': 'rider_location',
            'lat': event['lat'],
            'lng': event['lng']
        }))