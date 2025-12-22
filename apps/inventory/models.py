# apps/inventory/models.py
from django.db import models
from django.conf import settings
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse
from apps.utils.models import TimestampedModel # Assuming a common base model exists

class InventoryStock(TimestampedModel):
    """
    Physical + Logical stock representation.
    Uniqueness constraint on (warehouse, product) is critical.
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
    
    # Total physical quantity on shelf (including reserved)
    quantity = models.IntegerField(default=0)
    
    # Quantity currently locked for pending orders
    reserved_quantity = models.IntegerField(default=0)
    
    low_stock_threshold = models.IntegerField(default=10)

    class Meta:
        verbose_name = "Inventory Stock"
        unique_together = ('warehouse', 'product')
        indexes = [
            models.Index(fields=['warehouse', 'product']),
        ]

    @property
    def available_quantity(self):
        """
        Computed property for Read-Only display. 
        DO NOT use this for logic checks inside transactions; calculate manually from DB fields.
        """
        return max(0, self.quantity - self.reserved_quantity)

    def __str__(self):
        return f"{self.warehouse.code} - {self.product.sku_code}: {self.available_quantity}"


class StockMovementLog(TimestampedModel):
    """
    Immutable Ledger for all inventory changes.
    """
    class MovementType(models.TextChoices):
        INBOUND_GRN = "INBOUND", "Inbound (GRN)"
        OUTBOUND_ORDER = "OUTBOUND", "Outbound (Order)"
        RESERVATION = "RESERVE", "Reservation"
        RELEASE = "RELEASE", "Release (Cancellation)"
        ADJUSTMENT = "ADJUST", "Audit Adjustment"

    inventory = models.ForeignKey(
        InventoryStock, 
        on_delete=models.CASCADE, 
        related_name='logs'
    )
    quantity_change = models.IntegerField(help_text="Negative for deductions, Positive for additions")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    
    # Context
    reference = models.CharField(max_length=100, db_index=True, help_text="Order ID, GRN Number, etc.")
    balance_after = models.IntegerField(help_text="Physical Quantity after change")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ['-created_at']