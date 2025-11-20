from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PhoneOTP, RiderProfile, CustomerProfile, EmployeeProfile

User = get_user_model()

def normalize_phone(phone):
    # TODO: Implement phone number normalization logic
    return phone

class RequestOTPSerializer(serializers.Serializer):
    """
    Serializer for requesting an OTP.
    """
    phone = serializers.CharField(max_length=15)
    login_type = serializers.ChoiceField(choices=[("CUSTOMER", "Customer"), ("RIDER", "Rider"), ("EMPLOYEE", "Employee")])

class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying an OTP.
    """
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    login_type = serializers.ChoiceField(choices=[("CUSTOMER", "Customer"), ("RIDER", "Rider"), ("EMPLOYEE", "Employee")])

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for basic user details.
    """
    class Meta:
        model = User
        fields = ['id', 'phone', 'full_name', 'email', 'profile_picture']

class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderProfile
        fields = ['id', 'on_duty', 'on_delivery', 'rating', 'cash_on_hand']

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
    status = serializers.ChoiceField(choices=RiderProfile.RiderStatus.choices)

class AdminCreateEmployeeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    employee_code = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=EmployeeProfile.Role.choices)
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