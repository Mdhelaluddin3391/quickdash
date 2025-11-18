# apps/inventory/models.py
from django.db import models
from apps.catalog.models import SKU

class InventoryStock(models.Model):
    """
    Tracks total stock of an SKU in a specific Warehouse.
    Source of Truth for 'Availability' (Can we sell this?).
    """
    id = models.BigAutoField(primary_key=True)
    # Warehouse ko string reference se refer kar rahe hain
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.CASCADE, related_name='stocks')
    
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='warehouse_stocks')
    
    available_qty = models.IntegerField(default=0) # Bechne ke liye kitna bacha hai
    reserved_qty = models.IntegerField(default=0)  # Orders ke liye kitna roka hua hai
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'sku')
        indexes = [models.Index(fields=['warehouse', 'sku'])]
        verbose_name_plural = "Inventory Stocks"

    def __str__(self):
        return f"{self.warehouse_id} / {self.sku.sku_code}: Avl={self.available_qty} (Res={self.reserved_qty})"