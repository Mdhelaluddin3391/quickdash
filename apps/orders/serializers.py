# apps/orders/serializers.py
from rest_framework import serializers
from .models import Order, OrderItem, OrderTimeline
from .models import Order, OrderItem, OrderTimeline, Cart, CartItem  # <-- Cart, CartItem add karofrom apps.catalog.models import SKU
from apps.warehouse.models import Warehouse
import uuid
# ===================================================================
#                      WRITE Serializers (Input)
# ===================================================================

class CreateOrderItemSerializer(serializers.Serializer):
    """
    Jab customer order create karega, toh har item ke liye
    sirf yeh do (2) cheezein bhejega.
    """
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_sku_id(self, value):
        # Check karein ki SKU database mein hai ya nahi
        if not SKU.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(f"SKU with id {value} does not exist or is inactive.")
        return value


class CreateOrderSerializer(serializers.Serializer):
    """
    Naya order create karne ke liye yeh main INPUT serializer hai.
    """
    warehouse_id = serializers.UUIDField()
    items = CreateOrderItemSerializer(many=True)
    delivery_address_json = serializers.JSONField() # Customer ka address
    # FIX: Add optional lat/lng fields
    delivery_lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    delivery_lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)


    def validate_warehouse_id(self, value):
        # Check karein ki Warehouse active hai ya nahi
        if not Warehouse.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(f"Warehouse with id {value} does not exist or is inactive.")
        return value

    def validate_items(self, value):
        # Check karein ki item list khaali na ho
        if not value:
            raise serializers.ValidationError("Order must contain at least one item.")
        
        # Check karein ki list mein duplicate SKUs na ho
        sku_ids = [item['sku_id'] for item in value]
        if len(sku_ids) != len(set(sku_ids)):
            raise serializers.ValidationError("Duplicate SKUs found in order items.")
        return value


# ===================================================================
#                       READ Serializers (Output)
# ===================================================================

class OrderItemSerializer(serializers.ModelSerializer):
    """
    Order details dikhaate waqt har item ko is format mein dikhayenge.
    """
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = (
            'sku', 
            'sku_code', 
            'sku_name_snapshot', 
            'quantity', 
            'unit_price', 
            'total_price'
        )


class OrderTimelineSerializer(serializers.ModelSerializer):
    """
    Order ki history (timeline) dikhane ke liye.
    """
    class Meta:
        model = OrderTimeline
        fields = ('status', 'timestamp', 'notes')


class OrderSerializer(serializers.ModelSerializer):
    """
    Customer ko poori order details (GET /api/v1/orders/<id>/) 
    dikhane ke liye.
    """
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'status',
            'payment_status',
            'final_amount',
            'total_amount',
            'discount_amount',
            'customer_phone',
            'warehouse_code',
            'created_at',
            'delivered_at',
            'delivery_address_json',
            'delivery_lat', 
            'delivery_lng', 
            'items',        # Nested list of items
            'timeline',     # Nested list of status changes
        )


class OrderListSerializer(serializers.ModelSerializer):
    """
    Customer ko uske "My Orders" page par sabhi orders ki 
    ek chhoti list (GET /api/v1/orders/) dikhane ke liye.
    """
    class Meta:
        model = Order
        fields = (
            'id', 
            'status', 
            'final_amount', 
            'created_at'
        )


class CartItemSerializer(serializers.ModelSerializer):
    sku_id = serializers.UUIDField(source='sku.id', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    sku_name = serializers.CharField(source='sku.name', read_only=True)
    sku_image = serializers.URLField(source='sku.image_url', read_only=True)
    price = serializers.DecimalField(source='sku.sale_price', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = CartItem
        fields = ['id', 'sku_id', 'sku_code', 'sku_name', 'sku_image', 'price', 'quantity', 'total_price']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_amount', 'updated_at']


class AddToCartSerializer(serializers.Serializer):
    """
    Cart mein item add/update karne ke liye input serializer.
    """
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=0) # 0 bhejne par item delete hoga