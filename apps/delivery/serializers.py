from rest_framework import serializers
from apps.orders.serializers import OrderSerializer # Order ki details dikhane ke liye
from .models import DeliveryTask, RiderProfile, RiderEarning

class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderProfile
        fields = ['id', 'is_online', 'on_delivery', 'rating', 'cash_on_hand']

class DeliveryTaskSerializer(serializers.ModelSerializer):
    # Order ki poori detail embedded (nested) dikhayenge
    order_details = OrderSerializer(source='order', read_only=True)
    
    class Meta:
        model = DeliveryTask
        fields = [
            'id', 'status', 'order_details', 
            'pickup_otp', 'delivery_otp', # Security ke liye inhe production mein hide kar sakte hain
            'created_at', 'accepted_at', 'picked_up_at', 'delivered_at'
        ]

class RiderEarningSerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source='created_at', format="%Y-%m-%d")
    
    class Meta:
        model = RiderEarning
        fields = ['id', 'order_id_str', 'base_fee', 'tip', 'total_earning', 'status', 'date']