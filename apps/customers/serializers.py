from rest_framework import serializers
from .models import Address

class AddressSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)
    
    # Read-only fields for API consumers
    location_lat = serializers.FloatField(source='location.y', read_only=True)
    location_lng = serializers.FloatField(source='location.x', read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "label",
            "address_line",
            "city",
            "pincode",
            "lat",
            "lng",
            "location_lat",
            "location_lng",
            "is_default",
        ]
        read_only_fields = ["id", "is_default"]

    def validate_lat(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_lng(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        
        # Delegate to Service Layer
        # Note: 'is_default' is handled via specific action, but we allow basic passing here if needed
        # For strictness, we ignore is_default in direct create and let service decide (first=true)
        
        from .services import CustomerService
        return CustomerService.create_address(
            user=user,
            label=validated_data['label'],
            address_line=validated_data['address_line'],
            city=validated_data.get('city', 'Bangalore'),
            pincode=validated_data['pincode'],
            lat=validated_data['lat'],
            lng=validated_data['lng']
        )