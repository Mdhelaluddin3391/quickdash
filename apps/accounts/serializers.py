from rest_framework import serializers
from .utils import normalize_phone


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)

    def validate_phone(self, value):
        return normalize_phone(value)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate_phone(self, value):
        return normalize_phone(value)

class AdminCreateRiderSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    vehicle_type = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_phone(self, value):
        return normalize_phone(value)


class AdminCreateEmployeeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    employee_code = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=EmployeeProfile.ROLE_CHOICES)
    warehouse_code = serializers.CharField(max_length=50)

    def validate_phone(self, value):
        return normalize_phone(value)


class AdminChangeStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField(max_length=16)