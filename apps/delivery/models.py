import uuid
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from apps.utils.models import TimestampedModel

class DeliveryJob(TimestampedModel):
    class Status(models.TextChoices):
        SEARCHING = "SEARCHING", "Searching for Rider"
        ASSIGNED = "ASSIGNED", "Rider Assigned"
        PICKED_UP = "PICKED_UP", "Picked Up"
        COMPLETED = "COMPLETED", "Delivered"
        FAILED = "FAILED", "Failed/Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Snapshot locations
    warehouse_location = gis_models.PointField(srid=4326)
    customer_location = gis_models.PointField(srid=4326)
    
    # Assigned Rider (linked to Auth User for now, RiderProfile in Step 8)
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        related_name='delivery_jobs'
    )
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SEARCHING)
    
    # Tracking
    pickup_time = models.DateTimeField(null=True, blank=True)
    completion_time = models.DateTimeField(null=True, blank=True)
    distance_meters = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job {self.order_id} - {self.status}"