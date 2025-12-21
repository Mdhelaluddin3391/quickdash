# apps/orders/models/order.py
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.warehouse.models import Warehouse

# ============================================
# Shared Enums
# ============================================

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("confirmed", "Confirmed"),
    ("picking", "Picking"),
    ("packed", "Packed"),
    ("ready", "Ready for Dispatch"),
    ("dispatched", "Dispatched"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
]

PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("authorized", "Authorized"),
    ("paid", "Paid"),
    ("refunded", "Refunded"),
]


class Coupon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_percentage = models.BooleanField(default=False)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "order_coupons"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["active", "valid_from", "valid_to"]),
        ]

    def __str__(self):
        return self.code

    def is_valid(self, amount: Decimal, when=None) -> bool:
        when = when or timezone.now()
        if not self.active:
            return False
        if not (self.valid_from <= when <= self.valid_to):
            return False
        if amount < self.min_purchase_amount:
            return False
        return True

    def calculate_discount(self, amount: Decimal) -> Decimal:
        if not self.is_valid(amount):
            return Decimal("0.00")
        if self.is_percentage:
            return (amount * self.discount_value / Decimal("100.0")).quantize(Decimal("0.01"))
        return min(self.discount_value, amount)


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PREPARING = 'preparing', _('Preparing')
        SHIPPED = 'shipped', _('Shipped')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')

    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=20, unique=True, editable=False)  # Human-readable ID (e.g., #ORD-1234)
    
    # Relationships
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='orders'
    )
    warehouse = models.ForeignKey(
        Warehouse, 
        on_delete=models.PROTECT, 
        related_name='orders'
    )

    # Delivery Data
    delivery_address_json = models.JSONField(
        default=dict, 
        help_text="Snapshot of full address at checkout"
    )
    delivery_city = models.CharField(max_length=100, blank=True, null=True)
    delivery_pincode = models.CharField(max_length=20, blank=True, null=True)
    delivery_lat = models.FloatField(blank=True, null=True)
    delivery_lng = models.FloatField(blank=True, null=True)

    # Financials (CRITICAL FIXES)
    # ---------------------------------------------------------------------
    # LOGIC FIX: Explicit final_amount FROZEN at checkout.
    # We do not rely on dynamic summing of items for historical accuracy.
    final_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        help_text="The exact amount shown to user at checkout (Frozen)."
    )

    # LOGIC FIX: Store Idempotency Keys and Gateway Metadata
    # Prevents 'Zombie Orders' and double-processing.
    metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="System metadata (Idempotency keys, debug info, gateway_response)"
    )
    # ---------------------------------------------------------------------

    # Status Flags
    status = models.CharField(
        max_length=20, 
        choices=OrderStatus.choices, 
        default=OrderStatus.PENDING,
        db_index=True
    )
    payment_status = models.CharField(
        max_length=20, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING,
        db_index=True
    )
    payment_gateway_order_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        db_index=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['customer', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_id:
            # Simple fallback ID generation if not handled by signal
            self.order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        """
        Helper to sum up OrderItems. 
        NOTE: Only use this during cart-to-order conversion. 
        After that, trust 'final_amount'.
        """
        total = self.items.aggregate(
            total=models.Sum('total_price')
        )['total'] or Decimal("0.00")
        
        self.final_amount = total
        if save:
            self.save(update_fields=['final_amount'])

    def __str__(self):
        return f"{self.order_id} ({self.customer.email or self.customer.phone})"