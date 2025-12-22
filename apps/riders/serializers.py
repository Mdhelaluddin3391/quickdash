from rest_framework import serializers
from .models import RiderProfile, RiderEarnings

class RiderProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source='user.phone', read_only=True)
    
    class Meta:
        model = RiderProfile
        fields = [
            'id', 'phone', 'is_online', 'is_available', 
            'vehicle_number', 'total_deliveries', 'rating'
        ]

class RiderEarningsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderEarnings
        fields = ['id', 'order_id', 'amount', 'description', 'created_at']

class LocationUpdateSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)