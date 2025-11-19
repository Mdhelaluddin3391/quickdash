import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.gis.geos import Point
from django.utils import timezone

# Logger setup (Production debugging ke liye zaroori)
logger = logging.getLogger(__name__)

class RiderLocationConsumer(AsyncJsonWebsocketConsumer):
    """
    Yeh Consumer Real-time Rider Tracking handle karega.
    Rider yahan connect karega aur location updates bhejega.
    """

    async def connect(self):
        """
        Jab Rider WebSocket connect karega.
        """
        self.user = self.scope["user"]

        # 1. Auth Check: Kya user logged in hai aur Rider hai?
        if self.user.is_anonymous or not self.user.is_rider:
            logger.warning(f"Unauthorized connection attempt: {self.user}")
            await self.close() # Connection reject kar do
            return

        # 2. Connection Accept karo
        await self.accept()
        
        # 3. Group mein add karo (Optional: Agar manager ko track karna ho)
        self.group_name = f"rider_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        
        logger.info(f"Rider {self.user.phone} connected to Location Stream.")

    async def disconnect(self, close_code):
        """
        Jab connection toot jaye (Network issue ya app close).
        """
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"Rider disconnected: {close_code}")

    async def receive_json(self, content):
        """
        Jab Rider App se data aayega: {"lat": 12.9716, "lng": 77.5946}
        """
        try:
            latitude = content.get("lat")
            longitude = content.get("lng")

            if latitude is not None and longitude is not None:
                # DB Update ko Async function ke through call karein
                await self.update_rider_location(latitude, longitude)
            else:
                await self.send_json({"error": "Invalid coordinates"})

        except Exception as e:
            logger.error(f"Error processing location: {e}")

    # --- Helper Methods (Database Interactions) ---
    # Note: Django ORM sync hota hai, isliye 'database_sync_to_async' use karna padta hai.

    @database_sync_to_async
    def update_rider_location(self, lat, lng):
        """
        RiderProfile ko update karta hai.
        """
        from apps.accounts.models import RiderProfile
        
        try:
            profile = self.user.rider_profile
            
            # GeoDjango Magic: Point create karo
            location_point = Point(float(lng), float(lat), srid=4326)
            
            profile.current_location = location_point
            profile.last_location_update = timezone.now()
            profile.save(update_fields=['current_location', 'last_location_update'])
            
            # (Optional) Yahan hum check kar sakte hain ki kya Rider 
            # Warehouse ya Customer ke paas pahunch gaya? (Geofencing)
            
        except RiderProfile.DoesNotExist:
            logger.error(f"RiderProfile missing for user {self.user.id}")