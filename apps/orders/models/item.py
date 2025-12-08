import uuid
import logging
from decimal import Decimal

from django.db import models

from .order import Order

logger = logging.getLogger(__name__)


class OrderItem(models.Model):
    """
    Order ke andar ek-ek line item.
    SKU snapshot + quantity + pricing store hota hai.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE,
    )
    sku = models.ForeignKey(
        "catalog.SKU",  # app_label = 'catalog'
        related_name="order_items",
        on_delete=models.PROTECT,
    )

    sku_name_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Warehouse short-pick
    short_qty = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_items"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self):
        return f"{self.sku_name_snapshot} x {self.quantity}"

    def save(self, *args, **kwargs):
        # unit_price missing ho to SKU se uthao
        if self.unit_price is None and self.sku_id:
            self.unit_price = getattr(self.sku, "sale_price", Decimal("0.00"))

        # total = unit * qty (short pick ka effect order ke totals mein handle hoga)
        self.total_price = (self.unit_price or Decimal("0.00")) * self.quantity

        super().save(*args, **kwargs)

        # Order totals recalc
        try:
            self.order.recalculate_totals(save=True)
        except Exception as e:
            # Best-effort; errors ko swallow karna zyada safe hai yahan
            logger.exception("Failed to recalculate order totals for order %s", self.order_id)
