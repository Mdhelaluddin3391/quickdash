import uuid
from django.db import models
from django.conf import settings
from .order import Order

class OrderTimeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, related_name="timeline", on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20)  # Stores the status *after* change
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-timestamp"]