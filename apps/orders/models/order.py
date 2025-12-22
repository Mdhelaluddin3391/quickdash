import uuid
from django.db import models
from django.conf import settings
from apps.utils.models import TimestampedModel

class Order(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        CONFIRMED = "CONFIRMED", "Confirmed (Paid)"
        PROCESSING = "PROCESSING", "Picking & Packing"
        READY_FOR_PICKUP = "READY", "Ready for Pickup"
        OUT_FOR_DELIVERY = "ON_WAY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.CharField(primary_key=True, max_length=50, editable=False) # Custom OrderID (e.g. ORD-123)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    
    # Snapshot of Address (JSON) to prevent historical drift
    delivery_address = models.JSONField()
    warehouse_id = models.UUIDField() 
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    # Idempotency & Payment Linking
    payment_id = models.CharField(max_length=100, blank=True, null=True, help_text="Razorpay Order ID")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.id} [{self.status}]"

    @property
    def can_cancel(self):
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]