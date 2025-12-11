from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from .models import PhoneOTP, UserSession, RiderProfile, EmployeeProfile, CustomerProfile, Address
from .utils import normalize_phone

User = get_user_model()

# ======================
# AUTH SERIALIZERS (NEW)
# ======================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token payload to include user Role and Name.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['name'] = user.full_name
        token['role'] = user.app_role or "CUSTOMER"
        token['is_staff'] = user.is_staff
        
        # Add session ID if available in context (passed from view)
        if hasattr(user, 'current_session_jti'):
            token['session_jti'] = user.current_session_jti

        return token

class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    role = serializers.ChoiceField(choices=[
        ('CUSTOMER', 'Customer'),
        ('RIDER', 'Rider'),
        ('EMPLOYEE', 'Employee')
    ])
    
    def validate_phone(self, value):
        return normalize_phone(value)

class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    role = serializers.ChoiceField(choices=[
        ('CUSTOMER', 'Customer'),
        ('RIDER', 'Rider'),
        ('EMPLOYEE', 'Employee')
    ])
    
    # Optional: Device info for Session tracking
    device_id = serializers.CharField(required=False, allow_blank=True)
    client_name = serializers.CharField(required=False, allow_blank=True)
    
    def validate_phone(self, value):
        return normalize_phone(value)

class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()


# ======================
# USER / PROFILE SERIALIZERS
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
# ADDRESS SERIALIZERS
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

    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Address
        fields = [
            'id',
            'user',
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
        read_only_fields = ['location', 'user', 'service_available', 'service_message', 'latitude', 'longitude']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.location:
            ret['lat'] = instance.location.y
            ret['lng'] = instance.location.x
        return ret

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None
    
    def get_service_available(self, obj):
        if not obj.location:
            return None
        try:
            from apps.warehouse.services import check_service_availability
            result = check_service_availability(obj.location.y, obj.location.x)
            return result.get('is_available', False)
        except Exception:
            return False
    
    def get_service_message(self, obj):
        if not obj.location:
            return None
        try:
            from apps.warehouse.services import check_service_availability
            result = check_service_availability(obj.location.y, obj.location.x)
            return result.get('message', '')
        except Exception:
            return ''

    def create(self, validated_data):
        lat = validated_data.pop('lat', None)
        lng = validated_data.pop('lng', None)

        if lat is not None and lng is not None:
            validated_data['location'] = Point(float(lng), float(lat), srid=4326)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat = validated_data.pop('lat', None)
        lng = validated_data.pop('lng', None)

        if lat is not None and lng is not None:
            instance.location = Point(float(lng), float(lat), srid=4326)

        return super().update(instance, validated_data)


class AddressListSerializer(AddressSerializer):
    class Meta(AddressSerializer.Meta):
        # Exclude expensive computed fields for list views
        fields = [
            f for f in AddressSerializer.Meta.fields 
            if f not in ('service_available', 'service_message')
        ]
        read_only_fields = ['location', 'user']


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['id']


class CustomerMeSerializer(serializers.Serializer):
    user = UserProfileSerializer()
    customer = CustomerProfileSerializer()
    addresses = AddressListSerializer(many=True)


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