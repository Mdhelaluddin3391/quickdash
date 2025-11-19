# apps/orders/models.py
import uuid
from django.db import models
from django.conf import settings

# Choices (Jaisa system design mein bataya gaya hai)
# 
ORDER_STATUS_CHOICES = [
    ("pending", "Pending")[cite_start],           # Order receive hua, payment baki [cite: 149]
    ("confirmed", "Confirmed"),       # Payment ho gaya, WMS ko bhej diya
    ("picking", "Picking")[cite_start],           # WMS mein picking shuru [cite: 150]
    ("packed", "Packed")[cite_start],             # WMS mein packing ho gayi [cite: 151]
    ("ready", "Ready for Dispatch")[cite_start],  # WMS se nikal gaya, rider ka intezaar [cite: 152]
    ("dispatched", "Dispatched")[cite_start],     # Rider ne utha liya [cite: 153]
    ("delivered", "Delivered")[cite_start],       # Customer ko mil gaya [cite: 154]
    ("cancelled", "Cancelled")[cite_start],       # Order cancel ho gaya [cite: 155]
]

# 
PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("authorized", "Authorized"),
    ("paid", "Paid"),
    ("refunded", "Refunded"),
]


class Order(models.Model):
    """
    [cite_start]Yeh main Order model hai. [cite: 106]
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # [cite_start]Kiska order hai? [cite: 108]
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="orders"
    )
    
    # [cite_start]Kahan se deliver hoga? [cite: 109]
    warehouse = models.ForeignKey(
        "warehouse.Warehouse", 
        on_delete=models.SET_NULL, 
        null=True,
        related_name="orders"
    )

    # [cite_start]Order ka status kya hai? [cite: 110]
    status = models.CharField(
        max_length=30, 
        choices=ORDER_STATUS_CHOICES, 
        default="pending",
        db_index=True
    )

    # [cite_start]Paise ka hisaab [cite: 111]
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # [cite_start]Payment ka status kya hai? [cite: 112]
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )
    payment_gateway_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    # [cite_start]WMS/Delivery waale log [cite: 113, 114]
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="packed_orders"
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="delivered_orders"
    )

    # [cite_start]Time kab-kab kya hua [cite: 115]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    promised_eta = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Customer ka address (copy karke save karna zaroori hai)
    delivery_address_json = models.JSONField(null=True, blank=True)
    delivery_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def recalculate_totals(self, save=True):
        """
        Centralized Logic for Money:
        Subtotal -> Discount -> Delivery -> Tax -> Final
        """
        # 1. Subtotal (Items ka total)
        self.item_subtotal = sum(item.total_price for item in self.items.all()) or Decimal('0.00')

        # 2. Delivery Fee (Logic: Base + Distance based)
        # (Yahan aap GeoDjango logic laga sakte hain distance calculate karne ke liye)
        self.delivery_fee = getattr(settings, 'BASE_DELIVERY_FEE', Decimal('20.00'))

        # 3. Discount (Coupon Logic)
        if self.coupon and self.coupon.is_valid(self.item_subtotal):
            self.discount_amount = self.coupon.calculate_discount(self.item_subtotal)
        else:
            self.discount_amount = Decimal('0.00')

        # 4. Tax Calculation (Post-Discount Value par)
        taxable_amount = self.item_subtotal - self.discount_amount
        tax_rate = getattr(settings, 'TAX_RATE', Decimal('0.05')) # 5%
        self.taxes_amount = (taxable_amount * tax_rate).quantize(Decimal('0.01'))

        # 5. Final Total
        self.final_total = (
            taxable_amount + 
            self.delivery_fee + 
            self.taxes_amount + 
            self.rider_tip
        ).quantize(Decimal('0.01'))
        
        # Negative protection
        if self.final_total < 0: self.final_total = Decimal('0.00')

        if save:
            self.save()

    def __str__(self):
        return f"Order {self.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    """
    Ek order mein kya-kya items they.
    """
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    
    sku = models.ForeignKey("catalog.SKU", on_delete=models.SET_NULL, null=True)
    
    # [cite_start]Item ki details (us time ki) [cite: 120, 121, 122]
    quantity = models.PositiveIntegerField() 
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) 
    total_price = models.DecimalField(max_digits=10, decimal_places=2) 
    
    # Jab order create hua, tab item ka naam kya tha (copy karke save karna)
    sku_name_snapshot = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.sku.sku_code if self.sku else 'N/A'}"
    
    def save(self, *args, **kwargs):
        # Jab bhi item save ho, uska naam snapshot karlo
        if self.sku and not self.sku_name_snapshot:
            self.sku_name_snapshot = self.sku.name
        # Total price calculate karlo
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('order', 'sku')


class OrderTimeline(models.Model):
    """
    Order ki poori history track karne ke liye.
    """
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")
    status = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")
    
    def __str__(self):
        return f"{self.order.id} @ {self.timestamp} -> {self.status}"

    class Meta:
        ordering = ['timestamp']



class Cart(models.Model):
    """
    Har customer ka ek hi active cart hoga.
    """
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.customer.phone}"

    @property
    def total_amount(self):
        # Cart ka total amount dynamic calculate karein
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    """
    Cart mein kya items hain.
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey("catalog.SKU", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'sku') # Ek SKU cart mein ek hi baar aayega (qty badhegi)

    @property
    def unit_price(self):
        return self.sku.sale_price

    @property
    def total_price(self):
        return self.sku.sale_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.sku.sku_code}"