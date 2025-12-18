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

        # Calculate new total
        new_total = (self.unit_price or Decimal("0.00")) * self.quantity
        
        # Check delta if updating
        old_total = Decimal("0.00")
        if self.pk:
            old_val = OrderItem.objects.filter(pk=self.pk).values('total_price').first()
            if old_val:
                old_total = old_val['total_price']
        
        delta = new_total - old_total
        
        self.total_price = new_total
        super().save(*args, **kwargs)

        # FIX: Efficient F() update instead of N+1 Sum Aggregation
        if delta != 0:
            from .order import Order
            from django.db.models import F
            
            # Update Subtotal
            Order.objects.filter(pk=self.order_id).update(
                total_amount=F('total_amount') + delta,
                updated_at=timezone.now()
            )
            
            # Trigger final calc (Tax/Discount) strictly on the Order object 
            # without re-summing items
            # We defer this to the view/service layer or call a lightweight method
            try:
                # Reload order to get new total_amount from DB before calculating tax/discount
                self.order.refresh_from_db(fields=['total_amount'])
                self.order.recalculate_totals(save=True, skip_aggregation=True)
            except Exception:
                logger.exception("Failed to recalculate order totals")