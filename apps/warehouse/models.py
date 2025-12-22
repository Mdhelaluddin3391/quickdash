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
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10)

    class Meta:
        unique_together = ('warehouse', 'code')

class Bin(models.Model):
    """
    Physical storage location (e.g., A1-B2).
    """
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='bins')
    bin_code = models.CharField(max_length=20, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.bin_code

class BinInventory(TimestampedModel):
    """
    Physical stock in a specific bin.
    """
    bin = models.ForeignKey(Bin, on_delete=models.PROTECT, related_name='inventory')
    sku = models.ForeignKey('catalog.SKU', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = ('bin', 'sku')
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0), 
                name='bin_inventory_qty_non_negative'
            )
        ]

class PickingTask(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    order_id = models.CharField(max_length=50, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        related_name='picking_tasks'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PickItem(models.Model):
    task = models.ForeignKey(PickingTask, on_delete=models.CASCADE, related_name='items')
    sku = models.ForeignKey('catalog.SKU', on_delete=models.PROTECT)
    bin = models.ForeignKey(Bin, on_delete=models.PROTECT)
    
    qty_to_pick = models.IntegerField()
    picked_qty = models.IntegerField(default=0)
    is_picked = models.BooleanField(default=False)

class PackingTask(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"

    picking_task = models.OneToOneField(PickingTask, on_delete=models.PROTECT, related_name='packing_task')
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        related_name='packing_tasks'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

class DispatchRecord(TimestampedModel):
    class Status(models.TextChoices):
        READY = "READY", "Ready for Pickup"
        ASSIGNED = "ASSIGNED", "Rider Assigned"
        HANDED_OVER = "HANDED_OVER", "Handed Over"

    picking_task = models.OneToOneField(PickingTask, on_delete=models.PROTECT, related_name='dispatch_record')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.READY)
    
    pickup_otp = models.CharField(max_length=6)
    rider_id = models.CharField(max_length=50, null=True, blank=True)

    # Denormalized for fast lookup
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    order_id = models.CharField(max_length=50, db_index=True)