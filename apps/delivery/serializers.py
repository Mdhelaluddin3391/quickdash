from rest_framework import serializers
from .models import DeliveryTask, RiderEarning
from apps.orders.serializers import OrderSerializer # Reusing existing order serializer

class DeliveryTaskSerializer(serializers.ModelSerializer):
    order_details = OrderSerializer(source='order', read_only=True)
    rider_name = serializers.CharField(source='rider.user.full_name', read_only=True)
    
    class Meta:
        model = DeliveryTask
        fields = [
            'id', 'status', 'rider_name', 'order_details', 
            'assigned_at', 'picked_up_at', 'delivered_at'
        ]

class OTPVerificationSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6)