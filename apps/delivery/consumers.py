import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DeliveryJob
# Assuming Order model import logic is handled inside methods to avoid circular async import issues

class DeliveryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group_name = f"delivery_{self.job_id}"
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        # [CRITICAL FIX] Auth Check
        if not await self.can_access_job(self.user, self.job_id):
            print(f"Unauthorized WS access: {self.user.id} -> {self.job_id}")
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def can_access_job(self, user, job_id):
        try:
            job = DeliveryJob.objects.select_related('rider').get(id=job_id)
            # 1. Is Rider?
            if job.rider == user:
                return True
            # 2. Is Customer? (Need to check Order)
            from apps.orders.models import Order
            order = Order.objects.filter(id=job.order_id, user=user).exists()
            return order
        except DeliveryJob.DoesNotExist:
            return False

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'location_update':
            # Only rider can send location
            if not await self.is_rider_for_job(self.user, self.job_id):
                return 

            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'delivery_location',
                    'lat': data['lat'],
                    'lng': data['lng']
                }
            )

    @database_sync_to_async
    def is_rider_for_job(self, user, job_id):
        return DeliveryJob.objects.filter(id=job_id, rider=user).exists()

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