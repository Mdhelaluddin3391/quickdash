import uuid
from django.db import models
# FIX: Order ka import hata diya
# from apps.orders.models import Order

PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("paid", "Paid"),
    ("failed", "Failed"),
]

REFUND_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("processed", "Processed"),
    ("failed", "Failed"),
]

class PaymentIntent(models.Model):
    """
    Har order ke liye ek payment attempt ko track karta hai.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Hamara internal Order ID
    # FIX: String reference ka istemaal kiya
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="payment_intents")
    
    # Payment Gateway (Razorpay) ka Order ID
    gateway_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Payment Gateway ka Payment ID (jab payment ho jaaye)
    gateway_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Payment ki rakam
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment ka status
    status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default="pending"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.gateway_order_id} for Order {self.order.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class Refund(models.Model):
    """
    WMS se aane waale refund requests ko track karta hai.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Kis payment ke against refund hai
    # FIX: String reference ka istemaal kiya
    payment = models.ForeignKey(
        "payments.PaymentIntent", 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="refunds"
    )
    
    # WMS se aane waali details
    # FIX: String reference ka istemaal kiya
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="refunds")
    pick_item_id = models.CharField(max_length=100, null=True, blank=True)
    reason = models.TextField(blank=True)
    
    # Refund ki rakam
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Refund ka status
    status = models.CharField(
        max_length=20, 
        choices=REFUND_STATUS_CHOICES, 
        default="pending"
    )
    
    # Gateway ka Refund ID
    gateway_refund_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Refund {self.id} for Order {self.order.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']