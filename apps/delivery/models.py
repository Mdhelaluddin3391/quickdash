import uuid
from django.db import models
from django.conf import settings
from apps.accounts.models import RiderProfile
from apps.warehouse.models import DispatchRecord
from apps.orders.models import Order

# Delivery Task ka status
DELIVERY_STATUS_CHOICES = [
    ("pending_assignment", "Pending Assignment"), # Order pack ho gaya, rider dhoondh rahe hain
    ("assigned", "Assigned to Rider"),         # Rider ko order mil gaya
    ("at_warehouse", "Rider at Warehouse"),      # Rider warehouse pahunch gaya
    ("picked_up", "Picked Up"),                # Rider ne order utha liya
    ("at_customer", "Rider at Customer"),      # Rider customer ke paas pahunch gaya
    ("delivered", "Delivered"),                # Order complete
    ("failed", "Failed Delivery"),             # Delivery fail ho gayi
]


class DeliveryTask(models.Model):
    """
    Yeh model ek order ko ek rider se jodta hai aur delivery ko track karta hai.
    Yeh system design mein 'delivery_assignments' [cite: 99] ko represent karta hai.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Order kahan se aaya? (WMS se)
    dispatch_record = models.OneToOneField(
        DispatchRecord, 
        on_delete=models.CASCADE,
        related_name="delivery_task"
    )
    
    # Kaunsa order hai? (Aasani se dhoondhne ke liye)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        related_name="delivery_tasks"
    )
    
    # Kis rider ko assign hua hai?
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True, # Shuru mein null hota hai
        related_name="delivery_tasks"
    )
    
    # Delivery ka status kya hai?
    status = models.CharField(
        max_length=30,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending_assignment",
        db_index=True
    )
    
    # Rider ke liye pickup OTP (Dispatch se copy kiya gaya)
    pickup_otp = models.CharField(max_length=10, blank=True)
    
    # Customer ke liye delivery OTP (hum generate karenge)
    delivery_otp = models.CharField(max_length=10, blank=True)

    # Time kab-kab kya hua
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Agar fail hua toh kyun?
    failed_reason = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Delivery for Order {self.order_id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class RiderLocation(models.Model):
    """
    Har rider ki last known location ko store karta hai.
    Yeh system design mein 'rider_locations'  ko represent karta hai.
    """
    rider = models.OneToOneField(
        RiderProfile,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="location"
    )
    
    # Rider ki 'on_duty' status (RiderProfile se copy)
    on_duty = models.BooleanField(default=False)
    
    # Rider ki last known location
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Location kab update hui thi
    timestamp = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Location for {self.rider.rider_code} (On Duty: {self.on_duty})"

    class Meta:
        indexes = [
            models.Index(fields=['on_duty', 'timestamp']),
        ]