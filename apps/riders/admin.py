from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import RiderProfile, Vehicle

@admin.register(RiderProfile)
class RiderProfileAdmin(OSMGeoAdmin):
    list_display = ('user_phone', 'current_status', 'is_approved', 'last_location_update')
    list_filter = ('current_status', 'is_approved')
    search_fields = ('user__phone', 'user__full_name')
    
    # Display raw lat/lng in admin for debugging
    readonly_fields = ('last_location_update',)

    def user_phone(self, obj):
        return obj.user.phone

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'vehicle_type', 'rider')
    search_fields = ('plate_number', 'rider__user__phone')