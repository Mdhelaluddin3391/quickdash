# apps/payments/models.py
from django.db import models
from django.conf import settings

class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        COD = 'COD', 'Cash on Delivery'
        RAZORPAY = 'RAZORPAY', 'Razorpay'
        
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESSFUL = 'SUCCESSFUL', 'Successful'
        FAILED = 'FAILED', 'Failed'
        REFUND_INITIATED = 'REFUND_INITIATED', 'Refund Initiated'
        REFUNDED = 'REFUNDED', 'Refunded'

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    # Important IDs
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="Payment Gateway ID (e.g. pay_Hj8...)")
    gateway_order_id = models.CharField(max_length=100, null=True, blank=True, help_text="Razorpay Order ID")
    
    # Debugging ke liye
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.id} - {self.status}"