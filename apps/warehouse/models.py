import uuid
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from apps.utils.models import TimestampedModel

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    address = models.TextField()
    
    # Geospatial
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    service_radius_km = models.FloatField(default=5.0)
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Zone(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=50) # e.g., "Cold Storage", "Ambient"
    code = models.CharField(max_length=10)

    class Meta:
        unique_together = ('warehouse', 'code')

class Bin(models.Model):
    """
    Physical storage location.
    Format: Zone-Aisle-Shelf-Bin (e.g., Z1-A01-S04-B10)
    """
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='bins')
    bin_code = models.CharField(max_length=20, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    
    # Capacity handling (optional, simplified for V1)
    capacity_units = models.IntegerField(default=100)

    def __str__(self):
        return self.bin_code

class BinInventory(TimestampedModel):
    """
    Physical stock in a specific bin.
    Source of Truth for Warehouse Operations.
    """
    bin = models.ForeignKey(Bin, on_delete=models.PROTECT, related_name='inventory')
    sku = models.ForeignKey('catalog.SKU', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = ('bin', 'sku')
        indexes = [
            models.Index(fields=['bin', 'sku']),
        ]

class PickingTask(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    order_id = models.CharField(max_length=50, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PickItem(models.Model):
    """
    Specific instruction: "Go to Bin X and pick 5 of SKU Y"
    """
    task = models.ForeignKey(PickingTask, on_delete=models.CASCADE, related_name='items')
    sku = models.ForeignKey('catalog.SKU', on_delete=models.PROTECT)
    bin = models.ForeignKey(Bin, on_delete=models.PROTECT)
    
    qty_to_pick = models.IntegerField()
    picked_qty = models.IntegerField(default=0)
    is_picked = models.BooleanField(default=False)

class DispatchRecord(TimestampedModel):
    """
    Final stage before handing over to Delivery Rider.
    """
    picking_task = models.OneToOneField(PickingTask, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='READY', db_index=True)
    pickup_otp = models.CharField(max_length=6) # Rider must verify this
    rider_assigned = models.ForeignKey('riders.RiderProfile', null=True, blank=True, on_delete=models.SET_NULL)