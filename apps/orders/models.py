import uuid
from django.db import models
from django.conf import settings

# Choices (Jaisa system design mein bataya gaya hai)
# 
ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),           # Order receive hua, payment baki
    ("confirmed", "Confirmed"),       # Payment ho gaya, WMS ko bhej diya
    ("picking", "Picking"),           # WMS mein picking shuru
    ("packed", "Packed"),             # WMS mein packing ho gayi
    ("ready", "Ready for Dispatch"),  # WMS se nikal gaya, rider ka intezaar
    ("dispatched", "Dispatched"),     # Rider ne utha liya
    ("delivered", "Delivered"),       # Customer ko mil gaya
    ("cancelled", "Cancelled"),       # Order cancel ho gaya
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
    Yeh main Order model hai, jaisa system design PDF [cite: 102] mein bataya gaya hai.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Kiska order hai?
    # [cite: 104]
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="orders"
    )
    
    # Kahan se deliver hoga?
    # [cite: 105]
    warehouse = models.ForeignKey(
        "warehouse.Warehouse", 
        on_delete=models.SET_NULL, 
        null=True,
        related_name="orders"
    )

    # Order ka status kya hai?
    # 
    status = models.CharField(
        max_length=30, 
        choices=ORDER_STATUS_CHOICES, 
        default="pending",
        db_index=True
    )

    # Paise ka hisaab
    # [cite: 107]
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment ka status kya hai?
    # 
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )
    payment_gateway_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    # WMS/Delivery waale log (jo baad mein update honge)
    # [cite: 109]
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="packed_orders"
    )
    # [cite: 110]
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="delivered_orders"
    )

    # Time kab-kab kya hua
    # [cite: 111]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    promised_eta = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Customer ka address (copy karke save karna zaroori hai)
    delivery_address_json = models.JSONField(null=True, blank=True)
    delivery_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)


    def __str__(self):
        return f"Order {self.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    """
    Ek order mein kya-kya items they. [cite: 112]
    """
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    
    # FIX: Point to the correct app 'catalog'
    sku = models.ForeignKey("catalog.SKU", on_delete=models.SET_NULL, null=True)
    # Item ki details (us time ki)
    # [cite: 116]
    quantity = models.PositiveIntegerField()
    # [cite: 117]
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # [cite: 118]
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
    Order ki poori history track karne ke liye. System Design 
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