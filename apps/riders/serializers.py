from rest_framework import serializers
from .models import RiderProfile, Vehicle

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['plate_number', 'vehicle_type', 'license_number', 'metadata']

class RiderProfileSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    
    current_lat = serializers.SerializerMethodField()
    current_lng = serializers.SerializerMethodField()

    class Meta:
        model = RiderProfile
        fields = [
            'id', 'phone', 'full_name', 'is_approved', 
            'current_status', 'current_lat', 'current_lng', 
            'earnings_wallet', 'vehicle'
        ]
        read_only_fields = ['is_approved', 'earnings_wallet']

    def get_current_lat(self, obj):
        return obj.current_location.y if obj.current_location else None

    def get_current_lng(self, obj):
        return obj.current_location.x if obj.current_location else None

class UpdateLocationSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)

class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['ONLINE', 'OFFLINE'])