import uuid
from django.db import models
from django.conf import settings
from apps.orders.models.order import Order

class PaymentMethod(models.TextChoices):
    RAZORPAY = "RAZORPAY", "Razorpay"
    STRIPE = "STRIPE", "Stripe"
    CASH_ON_DELIVERY = "COD", "Cash on Delivery"

class TransactionStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    PENDING = "PENDING", "Pending Provider"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='transactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.INITIATED)
    
    # Provider Fields
    provider_order_id = models.CharField(max_length=100, blank=True, help_text="Order ID from Razorpay/Stripe")
    provider_payment_id = models.CharField(max_length=100, blank=True, unique=True, null=True, help_text="Transaction ID from Provider")
    provider_signature = models.TextField(blank=True, null=True)
    
    # Audit
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider_order_id']),
            models.Index(fields=['provider_payment_id']),
        ]

    def __str__(self):
        return f"{self.payment_method} - {self.amount} - {self.status}"