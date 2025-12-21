import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Cart(models.Model):
    """
    Per-customer cart.
    Ek hi active cart per customer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="cart",
        on_delete=models.CASCADE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carts"

    def __str__(self):
        return f"Cart for {self.customer_id}"

    @property
    def total_amount(self) -> Decimal:
        total = self.items.aggregate(total=models.Sum("total_price"))["total"] or Decimal("0.00")
        return total


class CartItem(models.Model):
    """
    Cart ke andar ek item (SKU + quantity).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        Cart,
        related_name="items",
        on_delete=models.CASCADE,
    )
    sku = models.ForeignKey(
        "catalog.SKU",
        related_name="cart_items",
        on_delete=models.CASCADE,
    )

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        unique_together = ("cart", "sku")
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self):
        return f"{self.cart_id} -> {self.sku_id} x {self.quantity}"

    def save(self, *args, **kwargs):
        if self.unit_price is None and self.sku_id:
            self.unit_price = getattr(self.sku, "sale_price", Decimal("0.00"))

        self.total_price = (self.unit_price or Decimal("0.00")) * self.quantity
        super().save(*args, **kwargs)

        # cart.updated_at bump ho jayega auto_now se
