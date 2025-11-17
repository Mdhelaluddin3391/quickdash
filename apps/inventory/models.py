import uuid
from django.db import models
# FIX: Warehouse aur Bin ka import hata diya
# from apps.warehouse.models import Warehouse, Bin

class SKU(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, default='pcs')
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sku_code} - {self.name}"


class InventoryStock(models.Model):
    """
    FIX: Yeh model 'inventory' app mein rahega, kyonki yeh high-level
    warehouse stock track karta hai (bin-level nahi).
    """
    id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.CASCADE, related_name='stocks')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='warehouse_stocks')
    available_qty = models.IntegerField(default=0)  # not reserved
    reserved_qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'sku')
        indexes = [models.Index(fields=['warehouse', 'sku'])]

    def __str__(self):
        return f"{self.warehouse.code} / {self.sku.sku_code}: avl={self.available_qty} res={self.reserved_qty}"

# FIX: BinInventory model yahaan se HATA diya gaya hai.

# FIX: StockMovement model yahaan se HATA diya gaya hai.