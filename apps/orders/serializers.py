from rest_framework import serializers

from .models import (
    Order,
    OrderItem,
    OrderTimeline,
    Cart,
    CartItem,
    OrderCancellation,
)
from apps.catalog.models import SKU
from apps.warehouse.models import Warehouse


# ===================================================================
#                      WRITE Serializers (Input)
# ===================================================================


class CreateOrderItemSerializer(serializers.Serializer):
    """
    [LEGACY] Direct payload based order creation.
    Abhi hum primarily cart-based checkout use kar rahe hain,
    lekin agar kabhi direct items bhejne ho to use ho sakta hai.
    """
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_sku_id(self, value):
        if not SKU.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"SKU with id {value} does not exist or is inactive."
            )
        return value


class CreateOrderSerializer(serializers.Serializer):
    """
    Naya order create karne ke liye INPUT serializer.

    Current behavior:
    - Primary: Cart se items uthta hai (items optional)
    - Optional: items[] bhejo to future mein direct-flow add ho sakta hai
    """
    warehouse_id = serializers.UUIDField()
    items = CreateOrderItemSerializer(many=True, required=False)  # <-- OPTIONAL now
    delivery_address_json = serializers.JSONField()

    delivery_lat = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    delivery_lng = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    payment_method = serializers.ChoiceField(
        choices=(("RAZORPAY", "Razorpay"), ("COD", "Cash on Delivery")),
        required=False,
        default="RAZORPAY",
    )

    def validate_warehouse_id(self, value):
        if not Warehouse.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Warehouse with id {value} does not exist or is inactive."
            )
        return value

    def validate_items(self, value):
        # Only validate if client explicitly sends items
        if value is None:
            return value
        if not value:
            raise serializers.ValidationError("Order must contain at least one item.")

        sku_ids = [item["sku_id"] for item in value]
        if len(sku_ids) != len(set(sku_ids)):
            raise serializers.ValidationError("Duplicate SKUs found in order items.")
        return value


class AddToCartSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=0)

    def validate(self, attrs):
        sku_id = attrs["sku_id"]
        qty = attrs["quantity"]
        try:
            sku = SKU.objects.get(id=sku_id, is_active=True)
        except SKU.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive SKU.")

        if qty > sku.max_order_qty:
            raise serializers.ValidationError(
                f"Maximum {sku.max_order_qty} units allowed for this item."
            )
        return attrs

class PaymentVerificationSerializer(serializers.Serializer):
    """Validates payment gateway signature data (Razorpay)."""

    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()

    def validate(self, data):
        # Additional gateway verify view mein hota hai
        return data


class CancelOrderSerializer(serializers.Serializer):
    """
    Order cancel API input.
    """
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )


# ===================================================================
#                       READ Serializers (Output)
# ===================================================================


class OrderItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "sku",
            "sku_code",
            "sku_name_snapshot",
            "quantity",
            "unit_price",
            "total_price",
        )


class OrderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = ("status", "timestamp", "notes")


class OrderCancellationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderCancellation
        fields = ("reason", "reason_code", "cancelled_by", "created_at")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    cancellation = OrderCancellationSerializer(read_only=True)

    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "payment_status",
            "final_amount",
            "total_amount",
            "discount_amount",
            "customer_phone",
            "warehouse_code",
            "created_at",
            "delivered_at",
            "delivery_address_json",
            "delivery_lat",
            "delivery_lng",
            "items",
            "timeline",
            "cancellation",
        )


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "final_amount",
            "created_at",
        )


class CartItemSerializer(serializers.ModelSerializer):
    sku_id = serializers.UUIDField(source="sku.id", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_name = serializers.CharField(source="sku.name", read_only=True)
    sku_image = serializers.URLField(source="sku.image_url", read_only=True)
    price = serializers.DecimalField(
        source="sku.sale_price", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "sku_id",
            "sku_code",
            "sku_name",
            "sku_image",
            "price",
            "quantity",
            "total_price",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = ["id", "items", "total_amount", "updated_at"]
