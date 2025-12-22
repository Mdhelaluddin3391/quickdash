from rest_framework import serializers
from .models.order import Order, OrderStatus
from .models.item import OrderItem
from .models.cart import Cart, CartItem
from apps.catalog.serializers import ProductSerializer

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'total_price']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price']

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product_name_snapshot', 'quantity', 'unit_price_snapshot', 'subtotal']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'status', 'status_display', 'total_amount', 
            'delivery_address_snapshot', 'created_at', 'items'
        ]