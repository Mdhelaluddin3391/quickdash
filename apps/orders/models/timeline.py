from django.db import models
from .order import Order

class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, related_name='timeline', on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']