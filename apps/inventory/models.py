import uuid
from django.db import models
from apps.warehouse.models import Warehouse, Bin

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


class BinInventory(models.Model):
    id = models.BigAutoField(primary_key=True)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name='inventory')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='bin_inventories')
    qty = models.IntegerField(default=0)         # total qty physically present
    reserved_qty = models.IntegerField(default=0) # qty reserved for orders (not yet picked)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bin', 'sku')
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['bin']),
        ]

    def available_qty(self):
        return self.qty - self.reserved_qty

    def __str__(self):
        return f"{self.bin} / {self.sku.sku_code} => {self.qty} (res {self.reserved_qty})"


class InventoryStock(models.Model):
    id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='warehouse_stocks')
    available_qty = models.IntegerField(default=0)  # not reserved
    reserved_qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'sku')
        indexes = [models.Index(fields=['warehouse', 'sku'])]

    def __str__(self):
        return f"{self.warehouse.code} / {self.sku.sku_code}: avl={self.available_qty} res={self.reserved_qty}"


class StockMovement(models.Model):
    id = models.BigAutoField(primary_key=True)
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, null=True, on_delete=models.SET_NULL)
    change_type = models.CharField(max_length=50)  # sale, adjustment, return, purchase
    delta_qty = models.IntegerField()
    reference_type = models.CharField(max_length=50, null=True, blank=True)  # order, purchase_order
    reference_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['sku']), models.Index(fields=['warehouse']), models.Index(fields=['created_at'])]
