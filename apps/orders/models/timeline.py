import uuid

from django.conf import settings
from django.db import models

from .order import Order, ORDER_STATUS_CHOICES


class OrderTimeline(models.Model):
    """
    Order ki full history: status changes, notes, meta, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        related_name="timeline",
        on_delete=models.CASCADE,
    )
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    meta = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="order_timeline_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "order_timeline"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["order", "timestamp"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.order_id} → {self.status} @ {self.timestamp}"
