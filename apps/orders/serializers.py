from rest_framework import serializers
from .models import Order, OrderItem, OrderTimeline

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['sku_name_snapshot', 'unit_price_snapshot', 'quantity', 'total_price']

class OrderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = ['status', 'timestamp', 'note']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'status', 'total_amount', 
            'delivery_address_snapshot', 'created_at', 'items', 'timeline'
        ]

class CreateOrderSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()
    address_id = serializers.IntegerField()
    payment_method = serializers.CharField(max_length=20)