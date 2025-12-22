import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.utils.models import TimestampedModel

class DeliveryTask(TimestampedModel):
    """
    Manages the lifecycle of a delivery from Warehouse to Customer.
    """
    class DeliveryStatus(models.TextChoices):
        PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT", "Pending Assignment"
        ASSIGNED = "ASSIGNED", "Assigned to Rider"
        ACCEPTED = "ACCEPTED", "Accepted by Rider"
        AT_STORE = "AT_STORE", "Rider at Store"
        PICKED_UP = "PICKED_UP", "Picked Up"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    order = models.OneToOneField('orders.Order', on_delete=models.PROTECT, related_name='delivery_task')
    rider = models.ForeignKey('accounts.RiderProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    
    # State
    status = models.CharField(
        max_length=32,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING_ASSIGNMENT,
        db_index=True
    )
    
    # Metadata
    dispatch_record_id = models.CharField(max_length=100, null=True, blank=True, help_text="Link to WMS Dispatch")
    
    # Security
    pickup_otp = models.CharField(max_length=6, blank=True)   # Verifies Rider picked up from Store
    delivery_otp = models.CharField(max_length=6, blank=True) # Verifies Customer received package

    # Timestamps for SLA tracking
    assigned_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Feedback
    rating = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback = models.TextField(blank=True)

    def __str__(self):
        return f"Task {self.id} | {self.status}"

class RiderEarning(TimestampedModel):
    """
    Financial record for a completed delivery.
    """
    rider = models.ForeignKey('accounts.RiderProfile', on_delete=models.PROTECT, related_name="earnings")
    delivery_task = models.OneToOneField(DeliveryTask, on_delete=models.PROTECT, related_name="earning")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    is_settled = models.BooleanField(default=False)
    settlement_ref = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.rider} - {self.amount}"