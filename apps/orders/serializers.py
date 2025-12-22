from rest_framework import serializers
from .models import Order, OrderItem, OrderTimeline

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product_name', 'sku_code', 'quantity', 'unit_price', 'total_price']

class OrderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = ['status', 'description', 'created_at']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'status', 'payment_status', 'total_amount', 
            'delivery_fee', 'created_at', 'items', 'timeline',
            'delivery_address'
        ]

class CartItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    sku_code = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)

class CreateOrderSerializer(serializers.Serializer):
    address_id = serializers.UUIDField()
    items = CartItemSerializer(many=True)