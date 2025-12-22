import uuid
from django.db import models
from django.conf import settings
from apps.orders.models import Order
from apps.utils.models import TimestampedModel

class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"

class PaymentMethod(models.TextChoices):
    RAZORPAY = "RAZORPAY", "Razorpay"
    STRIPE = "STRIPE", "Stripe"
    COD = "COD", "Cash on Delivery"

class PaymentIntent(TimestampedModel):
    """
    Tracks the initialization of a payment request with the Gateway.
    """
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payment_intents")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    
    # Gateway specific IDs (e.g., 'order_N7sl2...')
    gateway_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Intent {self.gateway_order_id} - {self.status}"

class Payment(TimestampedModel):
    """
    Represents a successful or attempted transaction.
    """
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    payment_intent = models.ForeignKey(PaymentIntent, on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    
    # The actual transaction ID from provider (e.g., 'pay_2983...')
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    status = models.CharField(max_length=20, choices=PaymentStatus.choices)
    
    # Audit fields
    error_message = models.TextField(blank=True, null=True)
    gateway_response = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['transaction_id', 'status']),
        ]

    def __str__(self):
        return f"{self.transaction_id} | {self.amount} | {self.status}"

class WebhookLog(TimestampedModel):
    """
    Idempotency store for Webhook Events.
    """
    event_id = models.CharField(max_length=100, unique=True, help_text="Unique ID from Provider")
    provider = models.CharField(max_length=20, default="RAZORPAY")
    is_processed = models.BooleanField(default=False)
    payload = models.JSONField()

    def __str__(self):
        return f"{self.provider} - {self.event_id}"