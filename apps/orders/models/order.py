import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

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
    """
    Discount Coupon Model
    - Flat amount or percentage
    - Min purchase amount
    - Active window + usage counter
    """

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
    """
    Core Order aggregate.

    Yeh model actual commerce ke flows ko support karta hai:
    - Status lifecycle
    - Payment status
    - Totals (subtotal, discount, tax, delivery fee, final)
    - Warehouse + customer links
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.PROTECT,
    )
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",  # app_label 'warehouse' assume kiya gaya
        related_name="orders",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )

    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="pending")
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    # Amounts
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    taxes_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    rider_tip = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Coupon
    coupon = models.ForeignKey(
        Coupon,
        related_name="orders",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    payment_gateway_order_id = models.CharField(
        max_length=100, null=True, blank=True, help_text="Razorpay order id (if any)"
    )

    # Address + geo
    delivery_address_json = models.JSONField(default=dict)
    delivery_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Ops users
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="packed_orders",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="delivered_orders",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["payment_status", "created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order {self.id}"

    # ----------------------------------------------------
    # Totals calculation
    # ----------------------------------------------------
    def recalculate_totals(self, save: bool = False):
        """
        Items ke basis par subtotal nikaale, fir coupon/tax/delivery fee apply kare.
        """
        from .item import OrderItem  # local import to avoid circular

        subtotal = (
            OrderItem.objects.filter(order=self).aggregate(
                total=models.Sum("total_price")
            )["total"]
            or Decimal("0.00")
        )

        self.total_amount = subtotal

        # Base discount only from coupon (agar future main aur promos ho, yahan add karo)
        discount = Decimal("0.00")
        if self.coupon and self.coupon.is_valid(subtotal):
            discount = self.coupon.calculate_discount(subtotal)

        self.discount_amount = discount

        # Simple tax model: 0 for now (future: GST etc.)
        self.taxes_amount = self.taxes_amount or Decimal("0.00")
        self.delivery_fee = self.delivery_fee or Decimal("0.00")
        self.rider_tip = self.rider_tip or Decimal("0.00")

        self.final_amount = (
            subtotal
            - discount
            + self.taxes_amount
            + self.delivery_fee
            + self.rider_tip
        )

        if save:
            self.save(update_fields=[
                "total_amount",
                "discount_amount",
                "taxes_amount",
                "delivery_fee",
                "rider_tip",
                "final_amount",
                "updated_at",
            ])
