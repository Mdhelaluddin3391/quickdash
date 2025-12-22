import uuid
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from apps.utils.models import TimestampedModel

class RiderProfile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rider_profile')
    
    # Status
    is_approved = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False, help_text="Rider toggle: I am ready to work")
    is_available = models.BooleanField(default=False, help_text="System calculated: Online AND not busy")
    
    # Live Tracking
    current_location = gis_models.PointField(srid=4326, null=True, blank=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    
    # Vehicle Info
    vehicle_number = models.CharField(max_length=20, blank=True)
    vehicle_type = models.CharField(max_length=20, default="BIKE")
    
    # Metrics
    total_deliveries = models.IntegerField(default=0)
    rating = models.FloatField(default=5.0)

    def __str__(self):
        return f"{self.user.phone} - {'Online' if self.is_online else 'Offline'}"

class RiderEarnings(TimestampedModel):
    """
    Ledger for Rider Payouts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(RiderProfile, on_delete=models.PROTECT, related_name='earnings')
    
    order_id = models.CharField(max_length=50) # Link to Order
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    description = models.CharField(max_length=255) # e.g., "Delivery Fee for Order #123"

    class Meta:
        ordering = ['-created_at']