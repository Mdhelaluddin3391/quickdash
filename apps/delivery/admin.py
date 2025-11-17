from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import DeliveryTask, RiderLocation

@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.admin.ModelAdmin):
    """
    Delivery Task ko Admin Panel mein dikhane ke liye configuration.
    """
    list_display = (
        'id',
        'order',
        'rider',
        'status',
        'created_at',
        'picked_up_at',
        'delivered_at'
    )
    list_filter = ('status', 'created_at', 'rider')
    search_fields = ('id', 'order__id', 'rider__rider_code')
    
    # In fields ko admin mein badla nahi ja sakta
    readonly_fields = (
        'id',
        'dispatch_record',
        'order',
        'rider',
        'pickup_otp',
        'delivery_otp',
        'created_at',
        'assigned_at',
        'picked_up_at',
        'delivered_at',
    )

    def has_add_permission(self, request):
        # Admin se naya delivery task banana allow nahi hai
        return False


@admin.register(RiderLocation)
class RiderLocationAdmin(admin.admin.ModelAdmin):
    """
    Rider Location ko Admin Panel mein dikhane ke liye.
    """
    list_display = ('rider', 'on_duty', 'lat', 'lng', 'timestamp')
    list_filter = ('on_duty',)
    search_fields = ('rider__rider_code', 'rider__user__phone')
    
    # Location ko admin se edit nahi kar sakte
    readonly_fields = ('rider', 'lat', 'lng', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Location records ko delete nahi karna hai
        return False