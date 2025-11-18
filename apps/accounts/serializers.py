# apps/accounts/serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from .utils import normalize_phone
from .models import EmployeeProfile, RiderProfile


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    def validate_phone(self, value): return normalize_phone(value)

class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    def validate_phone(self, value): return normalize_phone(value)

# ===================================================================
#                      ADMIN MANAGEMENT SERIALIZERS
# ===================================================================

class AdminCreateRiderSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    vehicle_type = serializers.CharField(max_length=32, required=False)
    def validate_phone(self, value): return normalize_phone(value)

class AdminChangeRiderStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=RiderProfile.STATUS_CHOICES)

class AdminCreateEmployeeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    employee_code = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=EmployeeProfile.ROLE_CHOICES)
    warehouse_code = serializers.CharField(max_length=50)
    def validate_phone(self, value): return normalize_phone(value)

class AdminChangeEmployeeStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField(max_length=10) # 'ACTIVE' or 'INACTIVE'

# ===================================================================
#                      ADMIN PASSWORD RESET SERIALIZERS
# ===================================================================

class AdminForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255) # email or phone

class AdminResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(min_length=8)