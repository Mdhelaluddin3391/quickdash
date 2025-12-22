import uuid
from django.db import models
from django.conf import settings
from apps.warehouse.models import Warehouse

class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
    PAID = "PAID", "Paid & Confirmed"
    PROCESSING = "PROCESSING", "Packing"
    READY_FOR_PICKUP = "READY_FOR_PICKUP", "Ready for Rider"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"
    FAILED = "FAILED", "Payment Failed"

class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='orders')
    
    # Financials
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    # State
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT)
    payment_id = models.CharField(max_length=100, blank=True, null=True, help_text="Reference to Payment Transaction")
    
    # Delivery Info Snapshot
    delivery_address_snapshot = models.JSONField(help_text="Full address at time of order")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['warehouse', 'status']),
        ]

    def __str__(self):
        return f"Order #{str(self.id)[:8]} - {self.status}"