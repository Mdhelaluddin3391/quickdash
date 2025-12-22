from django.db import models
from django.conf import settings
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse
from apps.utils.models import TimestampedModel

class InventoryStock(TimestampedModel):
    """
    LOGICAL Inventory Source of Truth.
    Aggregates all physical bin counts for fast availability checks.
    """
    warehouse = models.ForeignKey(
        Warehouse, 
        on_delete=models.PROTECT, 
        related_name='inventory_stocks'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        related_name='inventory_stocks'
    )
    
    # Total on-hand (Physical count)
    quantity = models.IntegerField(default=0)
    
    # Locked for pending orders
    reserved_quantity = models.IntegerField(default=0)
    
    low_stock_threshold = models.IntegerField(default=10)

    class Meta:
        verbose_name = "Inventory Stock"
        unique_together = ('warehouse', 'product')
        indexes = [
            models.Index(fields=['warehouse', 'product']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0), 
                name='inventory_quantity_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(reserved_quantity__gte=0), 
                name='inventory_reserved_non_negative'
            ),
        ]

    @property
    def available_quantity(self):
        """
        Safe computation. 
        Note: Always use DB queries for critical logic, not this property.
        """
        return max(0, self.quantity - self.reserved_quantity)

    def __str__(self):
        return f"{self.warehouse.code} | {self.product.sku_code} | Avail: {self.available_quantity}"


class StockMovementLog(TimestampedModel):
    """
    Immutable Ledger of all inventory changes.
    """
    class MovementType(models.TextChoices):
        INBOUND_GRN = "INBOUND", "Inbound (GRN)"
        OUTBOUND_ORDER = "OUTBOUND", "Outbound (Order)"
        RESERVATION = "RESERVE", "Reservation"
        RELEASE = "RELEASE", "Release (Cancellation)"
        ADJUSTMENT = "ADJUST", "Manual Adjustment"
        RECONCILIATION = "RECON", "System Reconciliation"

    inventory = models.ForeignKey(
        InventoryStock, 
        on_delete=models.CASCADE, 
        related_name='logs'
    )
    
    quantity_change = models.IntegerField(help_text="Delta value (+/-)")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    
    # Traceability
    reference = models.CharField(max_length=100, db_index=True, help_text="Order ID, GRN, etc.")
    balance_after = models.IntegerField(help_text="Snapshot of physical qty")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ['-created_at']