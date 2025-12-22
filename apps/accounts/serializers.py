from rest_framework import serializers
from .models import User, Role

class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(min_length=10, max_length=15)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.CUSTOMER)

class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(min_length=10, max_length=15)
    otp = serializers.CharField(min_length=6, max_length=6)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.CUSTOMER)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone', 'full_name', 'email', 'role']