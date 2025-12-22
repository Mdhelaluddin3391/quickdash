from rest_framework import serializers
from .models import Payment, PaymentIntent, PaymentMethod

class CreatePaymentIntentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)

class PaymentIntentSerializer(serializers.ModelSerializer):
    key_id = serializers.SerializerMethodField()

    class Meta:
        model = PaymentIntent
        fields = ['id', 'gateway_order_id', 'amount', 'currency', 'status', 'key_id']

    def get_key_id(self, obj):
        # Return public key for frontend SDK
        from django.conf import settings
        return settings.RAZORPAY_KEY_ID