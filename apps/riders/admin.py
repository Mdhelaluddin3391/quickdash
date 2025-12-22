from django.contrib import admin
from .models import RiderProfile, RiderEarnings

@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_online', 'is_available', 'total_deliveries', 'last_heartbeat']
    list_filter = ['is_online', 'is_available']
    search_fields = ['user__phone', 'vehicle_number']

@admin.register(RiderEarnings)
class RiderEarningsAdmin(admin.ModelAdmin):
    list_display = ['rider', 'order_id', 'amount', 'created_at']
    search_fields = ['order_id', 'rider__user__phone']