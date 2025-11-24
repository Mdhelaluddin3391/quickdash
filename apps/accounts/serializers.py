from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import RiderProfile, EmployeeProfile, Address, CustomerProfile
from .models import RiderProfile, EmployeeProfile  # already imported



User = get_user_model()


# ======================
# Helper
# ======================

def normalize_phone(phone: str) -> str:
    from .utils import normalize_phone as _norm  # reuse utils :contentReference[oaicite:6]{index=6}
    return _norm(phone)


# ======================
# OTP SERIALIZERS
# ======================

class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    login_type = serializers.ChoiceField(
        choices=[
            ("CUSTOMER", "Customer"),
            ("RIDER", "Rider"),
            ("EMPLOYEE", "Employee"),
        ]
    )

    def validate_phone(self, value):
        return normalize_phone(value)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    login_type = serializers.ChoiceField(
        choices=[
            ("CUSTOMER", "Customer"),
            ("RIDER", "Rider"),
            ("EMPLOYEE", "Employee"),
        ]
    )

    def validate_phone(self, value):
        return normalize_phone(value)


# ======================
# BASIC USER / RIDER
# ======================

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'phone',
            'full_name',
            'email',
            'profile_picture',
            'app_role',
            'is_customer',
            'is_rider',
            'is_employee',
        ]


class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderProfile
        fields = [
            'id',
            'on_duty',
            'on_delivery',
            'rating',
            'cash_on_hand',
        ]


# ======================
# CUSTOMER SERIALIZERS
# ======================

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id',
            'address_type',
            'full_address',
            'landmark',
            'city',
            'pincode',
            'location',
            'is_default',
        ]


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['id']


class CustomerMeSerializer(serializers.Serializer):
    """
    Response for /customer/me/:
    - user basic info
    - customer profile id
    - addresses
    """
    user = UserProfileSerializer()
    customer = CustomerProfileSerializer()
    addresses = AddressSerializer(many=True)


# ======================
# ADMIN / EMPLOYEE MGMT (existing)
# ======================

class AdminCreateRiderSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    vehicle_type = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_phone(self, value):
        return normalize_phone(value)


class AdminChangeRiderStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=RiderProfile.RiderStatus.choices)


class AdminCreateEmployeeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255)
    employee_code = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=EmployeeProfile.Role.choices)
    warehouse_code = serializers.CharField(max_length=50)

    def validate_phone(self, value):
        return normalize_phone(value)


class AdminChangeEmployeeStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField(max_length=10)


class AdminForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=255,
        help_text="Email or phone",
    )


class AdminResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(min_length=8)


class ChangeUserRoleSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.CharField(max_length=50)





class RiderAdminListSerializer(serializers.ModelSerializer):
    """
    Admin ke liye Rider list / detail serializer.
    """
    phone = serializers.CharField(source="user.phone", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = RiderProfile
        fields = [
            "id",
            "phone",
            "full_name",
            "rider_code",
            "approval_status",
            "status",
            "vehicle_type",
            "on_duty",
            "on_delivery",
        ]


class EmployeeAdminListSerializer(serializers.ModelSerializer):
    """
    Admin / HR ke liye Employee list serializer.
    """
    phone = serializers.CharField(source="user.phone", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = [
            "id",
            "phone",
            "full_name",
            "employee_code",
            "role",
            "warehouse_code",
            "is_active_employee",
        ]
