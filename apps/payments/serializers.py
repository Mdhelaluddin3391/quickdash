# apps/payments/serializers.py
from rest_framework import serializers
from apps.orders.models import Order
from .models import PaymentIntent, Refund


class CreatePaymentIntentSerializer(serializers.Serializer):
    """
    Client sends: { "order_id": "..." }
    """
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value, status="pending")
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                "Order not found or is not in 'pending' state."
            )
        self.context["order"] = order
        return value


class VerifyPaymentSerializer(serializers.Serializer):
    """
    Client sends:
    {
        "payment_intent_id": "...",
        "gateway_payment_id": "...",
        "gateway_order_id": "...",
        "gateway_signature": "..."
    }
    """
    payment_intent_id = serializers.UUIDField()
    gateway_payment_id = serializers.CharField(max_length=100)
    gateway_order_id = serializers.CharField(max_length=100)
    gateway_signature = serializers.CharField(max_length=255)

    def validate_payment_intent_id(self, value):
        try:
            intent = PaymentIntent.objects.get(
                id=value,
                status=PaymentIntent.IntentStatus.PENDING,
            )
        except PaymentIntent.DoesNotExist:
            raise serializers.ValidationError(
                "PaymentIntent not found or already processed."
            )
        self.context["payment_intent"] = intent
        return value


class PaymentIntentSerializer(serializers.ModelSerializer):
    """
    API response for creating payment intent.
    """
    payment_intent_id = serializers.UUIDField(source="id")

    class Meta:
        model = PaymentIntent
        fields = (
            "payment_intent_id",
            "gateway_order_id",
            "amount",
            "currency",
        )


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = "__all__"
