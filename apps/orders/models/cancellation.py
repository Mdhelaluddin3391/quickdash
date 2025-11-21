from django.db import models


class OrderCancellation(models.Model):
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="cancellation")
    reason_code = models.CharField(max_length=50)
    reason_text = models.TextField(blank=True)
    cancelled_by = models.CharField(max_length=20, choices=[('CUSTOMER','CUSTOMER'),('SYSTEM','SYSTEM'),('OPS','OPS')])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cancellation for {self.order_id} by {self.cancelled_by}"
