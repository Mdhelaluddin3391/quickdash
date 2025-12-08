# apps/accounts/serializers.py
from rest_framework import serializers
import logging
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point 
from .models import RiderProfile, EmployeeProfile, Address, CustomerProfile

User = get_user_model()

logger = logging.getLogger(__name__)

# ======================
# Helper
# ======================

def normalize_phone(phone: str) -> str:
    from .utils import normalize_phone as _norm
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
    # Frontend se data LENE ke liye (Write)
    lat = serializers.FloatField(write_only=True, required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(write_only=True, required=False, min_value=-180, max_value=180)

    # Frontend ko data DENE ke liye (Read)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    # Service availability info
    service_available = serializers.SerializerMethodField(read_only=True)
    service_message = serializers.SerializerMethodField(read_only=True)

    # Read-only user show karne ke liye (optional but useful)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Address
        fields = [
            'id',
            'user',          # 👈 yeh add karo
            'address_type',
            'full_address',
            'landmark',
            'city',
            'pincode',
            'location',
            'is_default',
            'lat',
            'lng',
            'latitude',
            'longitude',
            'service_available',
            'service_message',
        ]
        read_only_fields = ['location', 'user', 'service_available', 'service_message']

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None
    
    def get_service_available(self, obj):
        """Check if this address location is serviceable"""
        if not obj.location:
            return None
        try:
            from apps.warehouse.services import check_service_availability
            result = check_service_availability(obj.location.y, obj.location.x)
            return result.get('is_available', False)
        except Exception as e:
            logger.exception("Service availability check failed: %s", e)
            # Return False (not available) when the service check fails to avoid 500s
            return False
    
    def get_service_message(self, obj):
        """Get service availability message"""
        if not obj.location:
            return None
        try:
            from apps.warehouse.services import check_service_availability
            result = check_service_availability(obj.location.y, obj.location.x)
            return result.get('message', '')
        except Exception as e:
            logger.exception("Service availability message retrieval failed: %s", e)
            return ''

    def create(self, validated_data):
        """
        lat/lng se Point banana + baaki data save karna.
        NOTE: user ko viewset ke perform_create se inject karenge.
        """
        lat = validated_data.pop('lat', None)
        lng = validated_data.pop('lng', None)

        if lat is not None and lng is not None:
            validated_data['location'] = Point(float(lng), float(lat), srid=4326)

        # yahan user already aayega: serializer.save(user=request.user) se
        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat = validated_data.pop('lat', None)
        lng = validated_data.pop('lng', None)

        if lat is not None and lng is not None:
            instance.location = Point(float(lng), float(lat), srid=4326)

        return super().update(instance, validated_data)


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['id']


class CustomerMeSerializer(serializers.Serializer):
    user = UserProfileSerializer()
    customer = CustomerProfileSerializer()
    addresses = AddressSerializer(many=True)


# ======================
# ADMIN / EMPLOYEE MGMT
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
    identifier = serializers.CharField(max_length=255, help_text="Email or phone")


class AdminResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(min_length=8)


class ChangeUserRoleSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.CharField(max_length=50)


class RiderAdminListSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = RiderProfile
        fields = [
            "id", "phone", "full_name", "rider_code", "approval_status",
            "status", "vehicle_type", "on_duty", "on_delivery",
        ]


class EmployeeAdminListSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = [
            "id", "phone", "full_name", "employee_code", "role",
            "warehouse_code", "is_active_employee",
        ]