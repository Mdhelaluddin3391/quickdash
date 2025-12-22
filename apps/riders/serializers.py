from rest_framework import serializers
from .models import RiderProfile, Vehicle

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['plate_number', 'vehicle_type', 'license_number']

class RiderProfileSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = RiderProfile
        fields = [
            'id', 'phone_number', 'full_name', 'is_approved', 
            'current_status', 'current_lat', 'current_lng', 'vehicle'
        ]