from django.db import models
from .order import Order

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_id = models.UUIDField()
    product_name = models.CharField(max_length=255)
    sku_code = models.CharField(max_length=50)
    
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.sku_code} x {self.quantity}"