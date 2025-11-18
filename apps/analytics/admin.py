# apps/analytics/admin.py
from django.contrib import admin
from .models import DailyKPI

@admin.register(DailyKPI)
class DailyKPIAdmin(admin.ModelAdmin):
    list_display = (
        'date', 
        'warehouse', 
        'total_orders', 
        'total_revenue', 
        'fulfillment_rate', 
        'avg_delivery_time_min'
    )
    list_filter = ('date', 'warehouse')
    search_fields = ('date',)
    readonly_fields = ('created_at', 'updated_at')