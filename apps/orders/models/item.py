from django.db import models


class OrderItem(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey("catalog.SKU", on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    sku_name_snapshot = models.CharField(max_length=255, blank=True)
    picked_qty = models.PositiveIntegerField(default=0)
    short_qty = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.quantity} x {self.sku.sku_code if self.sku else 'N/A'}"
    
    def save(self, *args, **kwargs):
        if self.sku and not self.sku_name_snapshot:
            self.sku_name_snapshot = getattr(self.sku, 'name', '')
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        # Recalculate order totals if order relation exists
        try:
            if self.order:
                # avoid importing here to prevent circulars; use relation
                self.order.recalculate_totals(save=True)
        except Exception:
            pass

    class Meta:
        unique_together = ('order', 'sku')
