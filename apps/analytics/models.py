# apps/analytics/models.py
import uuid
from decimal import Decimal
from django.db import models


class BaseSnapshot(models.Model):
    """
    Common base for snapshot tables (for easier extension).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class DailySalesSummary(BaseSnapshot):
    """
    Daily sales per day (global).
    """
    total_orders = models.PositiveIntegerField(default=0)
    total_paid_orders = models.PositiveIntegerField(default=0)
    total_cancelled_orders = models.PositiveIntegerField(default=0)

    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_refund_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    avg_order_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        unique_together = ("date",)
        verbose_name = "Daily Sales Summary"
        verbose_name_plural = "Daily Sales Summaries"

    def __str__(self):
        return f"SalesSummary({self.date})"


class WarehouseKPISnapshot(BaseSnapshot):
    """
    Per-warehouse daily KPIs.
    """
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.CASCADE,
        related_name="kpi_snapshots",
    )

    orders_created = models.PositiveIntegerField(default=0)
    orders_dispatched = models.PositiveIntegerField(default=0)
    orders_delivered = models.PositiveIntegerField(default=0)
    orders_cancelled = models.PositiveIntegerField(default=0)

    avg_pick_time_seconds = models.PositiveIntegerField(default=0)
    avg_pack_time_seconds = models.PositiveIntegerField(default=0)
    avg_dispatch_to_delivery_seconds = models.PositiveIntegerField(default=0)

    short_pick_incidents = models.PositiveIntegerField(default=0)
    full_cancellations = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("date", "warehouse")
        verbose_name = "Warehouse KPI Snapshot"
        verbose_name_plural = "Warehouse KPI Snapshots"

    def __str__(self):
        return f"WarehouseKPI({self.warehouse_id}, {self.date})"


class RiderKPISnapshot(BaseSnapshot):
    """
    Per-rider daily performance snapshot.
    """
    rider = models.ForeignKey(
        "accounts.RiderProfile",
        on_delete=models.CASCADE,
        related_name="kpi_snapshots",
    )

    tasks_assigned = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    tasks_failed = models.PositiveIntegerField(default=0)

    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    avg_delivery_time_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("date", "rider")
        verbose_name = "Rider KPI Snapshot"
        verbose_name_plural = "Rider KPI Snapshots"

    def __str__(self):
        return f"RiderKPI({self.rider_id}, {self.date})"


class SKUAnalyticsDaily(BaseSnapshot):
    """
    Per-SKU daily sales analytics (global, across warehouses).
    """
    sku = models.ForeignKey(
        "catalog.SKU",
        on_delete=models.CASCADE,
        related_name="daily_analytics",
    )

    quantity_sold = models.PositiveIntegerField(default=0)
    gross_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    avg_selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    orders_count = models.PositiveIntegerField(default=0)
    refunds_count = models.PositiveIntegerField(default=0)
    refunded_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("date", "sku")
        verbose_name = "SKU Daily Analytics"
        verbose_name_plural = "SKU Daily Analytics"

    def __str__(self):
        return f"SKUAnalytics({self.sku_id}, {self.date})"


class InventorySnapshotDaily(BaseSnapshot):
    """
    Daily inventory health per SKU per warehouse.

    Useful for:
    - aging stock
    - low-stock alerts (analytics side)
    """
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.CASCADE,
        related_name="inventory_snapshots",
    )
    sku = models.ForeignKey(
        "catalog.SKU",
        on_delete=models.CASCADE,
        related_name="inventory_snapshots",
    )

    closing_available_qty = models.IntegerField(default=0)
    closing_reserved_qty = models.IntegerField(default=0)

    class Meta:
        unique_together = ("date", "warehouse", "sku")
        verbose_name = "Inventory Daily Snapshot"
        verbose_name_plural = "Inventory Daily Snapshots"

    def __str__(self):
        return f"InventorySnapshot({self.warehouse_id}, {self.sku_id}, {self.date})"
