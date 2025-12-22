from django.db import models
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse

class WarehouseInventory(models.Model):
    """
    The intersection of Product and Warehouse.
    Represents actual physical stock in a specific location.
    """
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_stock')
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'product')
        indexes = [
            models.Index(fields=['warehouse', 'product']),
        ]
        verbose_name_plural = "Warehouse Inventories"

    @property
    def available_quantity(self):
        return max(0, self.quantity - self.reserved_quantity)

    def __str__(self):
        return f"{self.warehouse.name} - {self.product.name}: {self.available_quantity}"

class StockMovementLog(models.Model):
    """
    Audit trail for every stock change (Inbound/Outbound/Loss).
    """
    MOVEMENT_TYPES = (
        ('INBOUND', 'Inbound Restock'),
        ('OUTBOUND', 'Order Fulfillment'),
        ('RETURN', 'Customer Return'),
        ('ADJUSTMENT', 'Audit Adjustment'),
    )

    inventory = models.ForeignKey(WarehouseInventory, on_delete=models.CASCADE, related_name='logs')
    quantity_change = models.IntegerField()
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    reference_id = models.CharField(max_length=100, blank=True, help_text="Order ID or PO Number")
    created_at = models.DateTimeField(auto_now_add=True)