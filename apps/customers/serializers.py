from rest_framework import serializers
from .models import CustomerProfile, Address

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        exclude = ['customer', 'created_at', 'updated_at']
        read_only_fields = ['id']

class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    # Flatten core user fields for the frontend
    phone = serializers.CharField(source='user.phone', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ['id', 'phone', 'full_name', 'email', 'loyalty_points', 'addresses']