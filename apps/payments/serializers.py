from rest_framework import serializers
from .models import Transaction

class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    method = serializers.CharField(max_length=20)

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'status', 'provider_order_id', 'created_at']