from rest_framework import serializers
from .models import DeliveryJob

class DeliveryJobSerializer(serializers.ModelSerializer):
    warehouse_lat = serializers.FloatField(source='warehouse_location.y', read_only=True)
    warehouse_lng = serializers.FloatField(source='warehouse_location.x', read_only=True)
    customer_lat = serializers.FloatField(source='customer_location.y', read_only=True)
    customer_lng = serializers.FloatField(source='customer_location.x', read_only=True)

    class Meta:
        model = DeliveryJob
        fields = [
            'id', 'order_id', 'status', 'rider', 
            'warehouse_lat', 'warehouse_lng',
            'customer_lat', 'customer_lng',
            'created_at'
        ]