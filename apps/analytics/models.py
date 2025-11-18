# apps/analytics/models.py
from django.db import models
from apps.warehouse.models import Warehouse

class DailyKPI(models.Model):
    """
    Core performance metrics ko track karne ke liye model.
    Analytics queries ko OLTP database (PostgreSQL) se offload kiya jayega
    aur yahan store kiya jayega. [cite: 103]
    """
    date = models.DateField(unique=True)
    warehouse = models.ForeignKey(
        Warehouse, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="daily_kpis"
    )

    # Core Metrics
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fulfillment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00) # e.g., 98.50
    avg_delivery_time_min = models.IntegerField(default=0)
    
    # Inventory Metrics
    inventory_discrepancy_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Daily KPI"
        verbose_name_plural = "Daily KPIs"
        ordering = ['-date']
        unique_together = ('date', 'warehouse')

    def __str__(self):
        return f"KPI for {self.date} @ {self.warehouse.code if self.warehouse else 'Overall'}"