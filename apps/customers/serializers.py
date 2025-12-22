from rest_framework import serializers
from .models import CustomerProfile, Address

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
        read_only_fields = ('customer',)

class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ['id', 'phone_number', 'full_name', 'loyalty_points', 'addresses']