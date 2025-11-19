from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PhoneOTP, RiderProfile, CustomerProfile, EmployeeProfile

User = get_user_model()

class RequestOTPSerializer(serializers.Serializer):
    """
    Phone number accept karne ke liye.
    """
    phone = serializers.CharField(max_length=15)
    login_type = serializers.ChoiceField(choices=[("CUSTOMER", "Customer"), ("RIDER", "Rider"), ("EMPLOYEE", "Employee")])

class VerifyOTPSerializer(serializers.Serializer):
    """
    OTP Verify karne ke liye.
    """
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    login_type = serializers.ChoiceField(choices=[("CUSTOMER", "Customer"), ("RIDER", "Rider"), ("EMPLOYEE", "Employee")])

class UserProfileSerializer(serializers.ModelSerializer):
    """
    User ki basic details return karne ke liye.
    """
    class Meta:
        model = User
        fields = ['id', 'phone', 'full_name', 'email', 'profile_picture', 'app_role']
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