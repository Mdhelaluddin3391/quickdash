import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

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
    """Discount Coupon Model"""
    code = models.CharField(max_length=50, unique=True)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_percentage = models.BooleanField(default=False)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    times_used = models.PositiveIntegerField(default=0)

    def is_valid(self, cart_amount):
        now = timezone.now()
        return (
            self.active and
            self.valid_from <= now <= self.valid_to and
            cart_amount >= self.min_purchase_amount
        )

    def calculate_discount(self, cart_amount):
        if self.is_percentage:
            return (cart_amount * self.discount_value / 100).quantize(Decimal('0.01'))
        return min(self.discount_value, cart_amount)

    def __str__(self):
        return self.code

class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="orders")
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.SET_NULL, null=True, related_name="orders")
    status = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES, default="pending", db_index=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default="pending")
    payment_gateway_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    packer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="packed_orders")
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivered_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    promised_eta = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_address_json = models.JSONField(null=True, blank=True)
    delivery_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rider_tip = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    taxes_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    item_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def recalculate_totals(self, save=True):
        self.item_subtotal = sum(item.total_price for item in self.items.all()) or Decimal('0.00')
        self.total_amount = self.item_subtotal
        
        self.delivery_fee = getattr(settings, 'BASE_DELIVERY_FEE', Decimal('20.00'))

        if self.coupon and self.coupon.is_valid(self.item_subtotal):
            self.discount_amount = self.coupon.calculate_discount(self.item_subtotal)
        else:
            self.discount_amount = Decimal('0.00')

        taxable_amount = self.item_subtotal - self.discount_amount
        tax_rate = getattr(settings, 'TAX_RATE', Decimal('0.05'))
        self.taxes_amount = (taxable_amount * tax_rate).quantize(Decimal('0.01'))

        self.final_amount = max(
            Decimal('0.00'),
            taxable_amount + self.delivery_fee + self.taxes_amount + self.rider_tip
        ).quantize(Decimal('0.01'))
        
        if save:
            self.save()

    def __str__(self):
        return f"Order {self.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['payment_status', 'created_at']),
        ]

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey("catalog.SKU", on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField() 
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) 
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False) 
    sku_name_snapshot = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.sku.sku_code if self.sku else 'N/A'}"
    
    def save(self, *args, **kwargs):
        if self.sku and not self.sku_name_snapshot:
            self.sku_name_snapshot = self.sku.name
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        if self.order:
            self.order.recalculate_totals(save=True)

    class Meta:
        unique_together = ('order', 'sku')

class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")
    status = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")
    
    class Meta:
        ordering = ['timestamp']

class Cart(models.Model):
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey("catalog.SKU", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'sku')

    @property
    def total_price(self):
        return self.sku.sale_price * self.quantity
