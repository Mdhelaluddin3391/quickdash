# apps/payments/serializers.py
from rest_framework import serializers
from apps.orders.models import Order
from .models import PaymentIntent, Refund

# ===================================================================
#                      PAYMENT (Input)
# ===================================================================

class CreatePaymentIntentSerializer(serializers.Serializer):
    """
    Yeh serializer customer se order ID lega taaki hum payment shuru kar sakein.
    INPUT: { "order_id": "..." }
    """
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        # Check karein ki Order maujood hai aur "pending" state mein hai
        try:
            order = Order.objects.get(id=value, status="pending")
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or is not in 'pending' state.")
        
        # Order ko serializer ke context mein save karein taaki view use istemaal kar sake
        self.context['order'] = order
        return value


class VerifyPaymentSerializer(serializers.Serializer):
    """
    Jab customer Razorpay par payment kar dega, tab woh yeh details bhejega.
    INPUT: { "payment_intent_id": "...", "gateway_payment_id": "...", 
             "gateway_order_id": "...", "gateway_signature": "..." }
    """
    payment_intent_id = serializers.UUIDField()
    gateway_payment_id = serializers.CharField(max_length=100)
    gateway_order_id = serializers.CharField(max_length=100)
    gateway_signature = serializers.CharField(max_length=255)

    def validate_payment_intent_id(self, value):
        # Check karein ki PaymentIntent maujood hai aur "pending" hai
        try:
            intent = PaymentIntent.objects.get(id=value, status="pending")
        except PaymentIntent.DoesNotExist:
            raise serializers.ValidationError("PaymentIntent not found or already processed.")
        
        # Intent ko context mein save karein
        self.context['payment_intent'] = intent
        return value


# ===================================================================
#                      PAYMENT (Output)
# ===================================================================

class PaymentIntentSerializer(serializers.ModelSerializer):
    """
    Payment shuru karne ke baad, hum customer ko yeh details bhejenge.
    OUTPUT: { "payment_intent_id": "...", "gateway_order_id": "...", "amount": ... }
    """
    payment_intent_id = serializers.UUIDField(source='id')

    class Meta:
        model = PaymentIntent
        fields = (
            'payment_intent_id',  # Hamara internal ID
            'gateway_order_id',   # Razorpay ka Order ID
            'amount'              # Kitna paisa dena hai
        )

# ===================================================================
#                      REFUND (Internal)
# ===================================================================

class RefundSerializer(serializers.ModelSerializer):
    """
    (Yeh internal use ke liye hai)
    """
    class Meta:
        model = Refund
        fields = '__all__'