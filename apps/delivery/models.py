import uuid
from django.db import models
from django.conf import settings
from apps.accounts.models import RiderProfile
# from apps.warehouse.models import DispatchRecord # <-- FIX: Direct import hata diya
from apps.orders.models import Order

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
    
    # FIX: Foreign Key ke bajaaye ab hum simple ID store karenge
    # Taki WMS app se koi direct dependency na rahe
    dispatch_record_id = models.UUIDField(unique=True, db_index=True)
    
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        related_name="delivery_tasks"
    )
    
    rider = models.ForeignKey(
        RiderProfile,
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
        # order_id ab direct nahi milega, isliye dispatch_record_id dikhayenge
        return f"Delivery for Dispatch {self.dispatch_record_id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class RiderLocation(models.Model):
    rider = models.OneToOneField(
        RiderProfile,
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