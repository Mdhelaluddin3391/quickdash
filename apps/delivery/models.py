# apps/delivery/models.py
import uuid
from django.db import models

# Delivery Task ka status
DELIVERY_STATUS_CHOICES = [
    ("pending_assignment", "Pending Assignment"), 
    ("assigned", "Assigned to Rider"),
    ("at_warehouse", "Rider at Warehouse"),
    ("picked_up", "Picked Up"),
    ("at_customer", "Rider at Customer"),
    ("delivered", "Delivered"),
    ("failed", "Failed Delivery"),
]


class DeliveryTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # WMS se aane wala Dispatch ID
    dispatch_record_id = models.UUIDField(unique=True, db_index=True)
    
    # Order link (string reference)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        related_name="delivery_tasks"
    )
    
    # Rider link (string reference)
    rider = models.ForeignKey(
        "accounts.RiderProfile",
        on_delete=models.SET_NULL,
        null=True, blank=True, 
        related_name="delivery_tasks"
    )
    
    status = models.CharField(
        max_length=30,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending_assignment",
        db_index=True
    )
    
    pickup_otp = models.CharField(max_length=10, blank=True)
    delivery_otp = models.CharField(max_length=10, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    failed_reason = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Delivery for Dispatch {self.dispatch_record_id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class RiderLocation(models.Model):
    # Rider link (string reference)
    rider = models.OneToOneField(
        "accounts.RiderProfile",
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="location"
    )
    
    on_duty = models.BooleanField(default=False)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Location for {self.rider.rider_code} (On Duty: {self.on_duty})"

    class Meta:
        indexes = [
            models.Index(fields=['on_duty', 'timestamp']),
        ]