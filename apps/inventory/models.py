# apps/inventory/models.py
from django.db import models
from django.db.models import CheckConstraint, Q
from apps.catalog.models import SKU
from apps.warehouse.models import Warehouse

class InventoryStock(models.Model):
    id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="stocks",
    )
    sku = models.ForeignKey(
        SKU,
        on_delete=models.CASCADE,
        related_name="warehouse_stocks",
    )
    available_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("warehouse", "sku")
        indexes = [
            models.Index(fields=["warehouse", "sku"]),
            models.Index(fields=["sku"]),
        ]
        verbose_name = "Inventory Stock"
        verbose_name_plural = "Inventory Stocks"
        constraints = [
            CheckConstraint(
                check=Q(available_qty__gte=0), 
                name="inventory_stock_available_qty_gte_0"
            ),
            CheckConstraint(
                check=Q(reserved_qty__gte=0), 
                name="inventory_stock_reserved_qty_gte_0"
            ),
        ]

    @property
    def total_qty(self):
        return self.available_qty + self.reserved_qty

    def __str__(self):
        return f"{self.warehouse.code} / {self.sku.sku_code}: Avl={self.available_qty}"


class InventoryHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    stock = models.ForeignKey(
        InventoryStock,
        on_delete=models.CASCADE,
        related_name="history",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="inventory_history",
    )
    sku = models.ForeignKey(
        SKU,
        on_delete=models.CASCADE,
        related_name="inventory_history",
    )
    delta_available = models.IntegerField(default=0)
    delta_reserved = models.IntegerField(default=0)
    available_after = models.IntegerField()
    reserved_after = models.IntegerField()
    change_type = models.CharField(max_length=64, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["warehouse", "sku", "created_at"]),
            models.Index(fields=["change_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at} | {self.sku.sku_code} | {self.change_type}"