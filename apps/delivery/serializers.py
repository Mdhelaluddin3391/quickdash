# apps/delivery/serializers.py
from rest_framework import serializers

from apps.orders.serializers import OrderSerializer
from apps.accounts.models import RiderProfile
from .models import DeliveryTask, RiderEarning


class RiderProfileSerializer(serializers.ModelSerializer):
    """
    Rider dashboard ke liye compact view.
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
            "on_duty",
            "on_delivery",
        ]


class DeliveryTaskSerializer(serializers.ModelSerializer):
    """
    Rider app ke liye Delivery Task details.
    """
    order_details = OrderSerializer(source="order", read_only=True)

    class Meta:
        model = DeliveryTask
        fields = [
            "id",
            "status",
            "order_details",
            "pickup_otp",   # optionally hide in production
            "delivery_otp", # ideally NOT sent to rider app; here for debugging
            "created_at",
            "accepted_at",
            "picked_up_at",
            "delivered_at",
        ]
        read_only_fields = [
            "pickup_otp",
            "delivery_otp",
            "created_at",
            "accepted_at",
            "picked_up_at",
            "delivered_at",
        ]


class RiderEarningSerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(
        source="created_at",
        format="%Y-%m-%d",
        read_only=True,
    )

    class Meta:
        model = RiderEarning
        fields = [
            "id",
            "order_id_str",
            "base_fee",
            "tip",
            "total_earning",
            "status",
            "date",
        ]
