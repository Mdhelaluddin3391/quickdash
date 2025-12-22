from rest_framework import serializers
from .models import User, Role

class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    role = serializers.ChoiceField(choices=Role.choices)

class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)
    role = serializers.ChoiceField(choices=Role.choices)

class UserProfileSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'full_name', 'email', 'roles']

    def get_roles(self, obj):
        return [r.role for r in obj.roles.all()]