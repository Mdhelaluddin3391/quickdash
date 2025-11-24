# apps/inventory/models.py
from django.db import models
from apps.catalog.models import SKU


class InventoryStock(models.Model):
    """
    Central aggregated stock for an SKU in a specific Warehouse.

    - Warehouse/Bin me jo bhi physical movement hota hai (GRN, RESERVE, DISPATCH,
      CYCLE_COUNT, etc.), Warehouse app 'inventory_change_required' signal fire karta hai.
    - Inventory app sirf un signals ko consume karke is table ko update karta hai.
    - Isko direct manually change nahi karna (except emergency tools).
    """
    id = models.BigAutoField(primary_key=True)

    # Warehouse ko app label se refer (micro-service like decoupling)
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
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
            models.Index(fields=["available_qty"]),
            models.Index(fields=["updated_at"]),
        ]
        verbose_name = "Inventory Stock"
        verbose_name_plural = "Inventory Stocks"

    def __str__(self):
        return (
            f"{self.warehouse_id} / {self.sku.sku_code}: "
            f"Avl={self.available_qty} (Res={self.reserved_qty})"
        )

    @property
    def total_qty(self) -> int:
        """
        Total physical qty = available + reserved.
        """
        return self.available_qty + self.reserved_qty


class InventoryHistory(models.Model):
    """
    Every inventory change is logged here for audit, analytics, debugging.

    This is like an 'event store' for the Inventory microservice:
    - which signal (change_type) changed the stock?
    - kitna delta?
    - kis reference (order id, grn number, cycle count id) se aaya?
    """
    id = models.BigAutoField(primary_key=True)

    stock = models.ForeignKey(
        InventoryStock,
        on_delete=models.CASCADE,
        related_name="history",
    )

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
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

    change_type = models.CharField(
        max_length=64,
        blank=True,
        help_text="Logical change type from WMS (e.g. putaway, sale_dispatch, cycle_count_adjustment)",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Order ID / GRN Number / Task ID / etc.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["warehouse", "sku", "created_at"]),
            models.Index(fields=["change_type", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.created_at} | {self.warehouse_id}/{self.sku.sku_code} "
            f"ΔAvl={self.delta_available} ΔRes={self.delta_reserved} ({self.change_type})"
        )
