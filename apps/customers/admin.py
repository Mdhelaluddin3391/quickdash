from django.contrib import admin
from .models import CustomerProfile, Address

class AddressInline(admin.StackedInline):
    model = Address
    extra = 0

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user_phone', 'loyalty_points', 'created_at')
    search_fields = ('user__phone', 'user__full_name')
    inlines = [AddressInline]

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = 'Phone'

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'label', 'city', 'pincode', 'is_default')
    list_filter = ('label', 'city')
    search_fields = ('customer__user__phone', 'pincode')