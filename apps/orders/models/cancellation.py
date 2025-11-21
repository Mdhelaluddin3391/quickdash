import uuid

from django.conf import settings
from django.db import models

from .order import Order


CANCELLED_BY_CHOICES = [
    ("CUSTOMER", "Customer"),
    ("SYSTEM", "System"),
    ("OPS", "Operations"),
]


class OrderCancellation(models.Model):
    """
    Order cancellation ka canonical record.
    - Reason
    - किसने cancel किया (customer/system/ops)
    - Extra metadata (e.g. warehouse incident code, ticket id, etc.)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order,
        related_name="cancellation",
        on_delete=models.CASCADE,
    )

    reason = models.TextField(blank=True)
    reason_code = models.CharField(max_length=50, blank=True)

    cancelled_by = models.CharField(
        max_length=20, choices=CANCELLED_BY_CHOICES, default="SYSTEM"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    meta = models.JSONField(default=dict, blank=True)

    cancelled_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="orders_cancelled",
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "order_cancellations"
        indexes = [
            models.Index(fields=["cancelled_by", "created_at"]),
        ]

    def __str__(self):
        return f"Cancellation for {self.order_id} ({self.cancelled_by})"
