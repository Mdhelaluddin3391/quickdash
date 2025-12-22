from django.db import models
from .order import Order
from apps.catalog.models import Product

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    
    # Snapshot Critical Data
    sku_name_snapshot = models.CharField(max_length=255)
    unit_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    
    quantity = models.PositiveIntegerField()
    
    @property
    def total_price(self):
        return self.unit_price_snapshot * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.sku_name_snapshot}"