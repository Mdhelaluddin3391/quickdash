from rest_framework import serializers
from .models import DeliveryTask, RiderLocation
from apps.accounts.models import RiderProfile
from apps.orders.models import Order


# ===================================================================
#                      RIDER LOCATION (Input/Output)
# ===================================================================

class UpdateRiderLocationSerializer(serializers.ModelSerializer):
    """
    Rider App yeh serializer istemaal karke apni location aur status update karega.
    INPUT serializer.
    """
    lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    on_duty = serializers.BooleanField(required=True)

    class Meta:
        model = RiderLocation
        fields = ('lat', 'lng', 'on_duty')


class RiderLocationSerializer(serializers.ModelSerializer):
    """
    Admin ya doosre systems ko rider ki location dikhane ke liye.
    OUTPUT serializer.
    """
    rider_code = serializers.CharField(source='rider.rider_code', read_only=True)
    
    class Meta:
        model = RiderLocation
        fields = ('rider', 'rider_code', 'on_duty', 'lat', 'lng', 'timestamp')


# ===================================================================
#                      DELIVERY TASK (Output)
# ===================================================================

class DeliveryTaskSerializer(serializers.ModelSerializer):
    """
    Admin ya internal use ke liye Delivery Task ki poori detail.
    OUTPUT serializer.
    """
    rider_code = serializers.CharField(source='rider.rider_code', read_only=True, default=None)
    order_id_str = serializers.CharField(source='order.id', read_only=True)
    warehouse_code = serializers.CharField(source='dispatch_record.warehouse.code', read_only=True)
    customer_phone = serializers.CharField(source='order.customer.phone', read_only=True)
    
    class Meta:
        model = DeliveryTask
        fields = (
            'id',
            'order_id_str',
            'status',
            'rider',
            'rider_code',
            'warehouse_code',
            'customer_phone',
            'pickup_otp',
            'delivery_otp',
            'created_at',
            'assigned_at',
            'picked_up_at',
            'delivered_at',
            'failed_reason',
        )


class RiderDeliveryTaskSerializer(serializers.ModelSerializer):
    """
    Rider App ko uski current task ki detail dikhane ke liye.
    Yeh 'Order' model se customer ka address bhi lega.
    OUTPUT serializer.
    """
    order_id_str = serializers.CharField(source='order.id', read_only=True)
    customer_address = serializers.JSONField(source='order.delivery_address_json', read_only=True)
    customer_lat = serializers.DecimalField(source='order.delivery_lat', max_digits=9, decimal_places=6, read_only=True)
    customer_lng = serializers.DecimalField(source='order.delivery_lng', max_digits=9, decimal_places=6, read_only=True)
    
    warehouse_address = serializers.CharField(source='dispatch_record.warehouse.address', read_only=True)
    warehouse_lat = serializers.DecimalField(source='dispatch_record.warehouse.lat', max_digits=9, decimal_places=6, read_only=True)
    warehouse_lng = serializers.DecimalField(source='dispatch_record.warehouse.lng', max_digits=9, decimal_places=6, read_only=True)

    class Meta:
        model = DeliveryTask
        fields = (
            'id',
            'order_id_str',
            'status',
            'pickup_otp',     # Warehouse par dene ke liye
            'delivery_otp',   # Customer se lene ke liye
            
            # Warehouse ki details
            'warehouse_address',
            'warehouse_lat',
            'warehouse_lng',
            
            # Customer ki details
            'customer_address',
            'customer_lat',
            'customer_lng',

            # Timestamps
            'assigned_at',
            'picked_up_at',
        )