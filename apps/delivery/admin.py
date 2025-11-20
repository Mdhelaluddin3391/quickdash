# apps/delivery/admin.py
from django.contrib import admin
from .models import DeliveryTask, RiderEarning

@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
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
        'dispatch_record_id',
        'order',
        'rider',
        'pickup_otp',
        'delivery_otp',
        'created_at',
        'accepted_at',
        'picked_up_at',
        'delivered_at',
    )

    def has_add_permission(self, request):
        return False


@admin.register(RiderEarning)
class RiderEarningAdmin(admin.ModelAdmin):
    """
    Admin view for rider earnings.
    """
    list_display = ('rider', 'delivery_task', 'total_earning', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('rider__rider_code', 'rider__user__username')
    readonly_fields = ('rider', 'delivery_task', 'base_fee', 'tip', 'total_earning', 'created_at')

    def has_add_permission(self, request):
        return False