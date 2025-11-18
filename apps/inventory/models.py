import uuid
from django.db import models
# FIX: Import SKU from catalog now
from apps.catalog.models import SKU 

# --- DELETE THE OLD SKU CLASS FROM HERE ---

class InventoryStock(models.Model):
    """
    Tracks total stock of an SKU in a specific Warehouse.
    """
    id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.CASCADE, related_name='stocks')
    
    # FIX: SKU is now a foreign key to apps.catalog.models.SKU
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='warehouse_stocks')
    
    available_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'sku')
        indexes = [models.Index(fields=['warehouse', 'sku'])]

    def __str__(self):
        return f"{self.warehouse.code} / {self.sku.sku_code}: avl={self.available_qty}"