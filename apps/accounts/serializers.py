from rest_framework import serializers
from .utils import normalize_phone
from .models import EmployeeProfile


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)

    def validate_phone(self, value):
        return normalize_phone(value)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate_phone(self, value):
        return normalize_phone(value)


# ========== ADMIN SERIALIZERS ==========

class AdminCreateRiderSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    vehicle_type = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

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


class AdminChangeRiderStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField(max_length=16)  # ACTIVE / PENDING / SUSPENDED


class AdminChangeEmployeeStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField(max_length=16)  # ACTIVE / INACTIVE




class AdminForgotPasswordSerializer(serializers.Serializer):
    """
    Serializer to request a password reset for an admin.
    User pehchanne ke liye 'identifier' (email ya phone) leta hai.
    """
    identifier = serializers.CharField(max_length=255)


class AdminResetPasswordSerializer(serializers.Serializer):
    """
    Serializer to set a new password using a reset token.
    """
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(
        max_length=128, 
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_token(self, value):
        # Token ko yahaan validate nahi karenge, view mein karenge
        # taaki humein token object mil sake
        return value