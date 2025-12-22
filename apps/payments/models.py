import uuid
from django.db import models
from django.conf import settings
from apps.utils.models import TimestampedModel
from apps.orders.models import Order

class PaymentTransaction(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUND_INITIATED = "REFUND_INITIATED", "Refund Initiated"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='transactions')
    
    # Gateway specific
    gateway_order_id = models.CharField(max_length=100, db_index=True, help_text="Razorpay Order ID")
    gateway_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    gateway_signature = models.TextField(blank=True, null=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.order_id} - {self.status}"

class RefundRecord(TimestampedModel):
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.PROTECT, related_name='refunds')
    gateway_refund_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50) # processed, pending, failed
    notes = models.TextField(blank=True)

class WebhookEvent(models.Model):
    """
    Idempotency Log: Keeps track of processed webhook events.
    """
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)