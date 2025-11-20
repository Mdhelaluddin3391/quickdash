# apps/analytics/serializers.py
from rest_framework import serializers
from .models import DailyKPI

class DailyKPISerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    
    class Meta:
        model = DailyKPI
        fields = [
            'date',
            'warehouse',
            'warehouse_code',
            'total_orders',
            'total_revenue',
            'fulfillment_rate',
            'avg_delivery_time_min',
            'inventory_discrepancy_count',
        ]
        extra_kwargs = {
            'warehouse': {'write_only': True}
        }