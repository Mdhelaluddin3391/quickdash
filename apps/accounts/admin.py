# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, CustomerProfile, RiderProfile, EmployeeProfile,
    PhoneOTP, UserSession, PasswordResetToken, Address
)

# Inlines for related models
class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    verbose_name_plural = 'Customer Profile'
    fk_name = 'user'

class RiderProfileInline(admin.StackedInline):
    model = RiderProfile
    can_delete = False
    verbose_name_plural = 'Rider Profile'
    fk_name = 'user'

class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'Employee Profile'
    fk_name = 'user'

class AddressInline(admin.StackedInline):
    model = Address
    extra = 0
    can_delete = True
    verbose_name_plural = 'Addresses'

# Main User Admin Class
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'full_name', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('phone', 'email', 'full_name')
    ordering = ('phone',)
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('email', 'full_name', 'app_role')}),
        ('Roles Flags', {'fields': ('is_customer', 'is_rider', 'is_employee')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'fields': ('phone', 'password')}),
    )
    inlines = [CustomerProfileInline, RiderProfileInline, EmployeeProfileInline, AddressInline]
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields.pop('last_login', None)
        return form

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_type', 'city', 'pincode', 'is_default')
    list_filter = ('address_type', 'is_default', 'city')
    search_fields = ('user__phone', 'full_address', 'pincode')
    raw_id_fields = ('user',)

@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'login_type', 'otp_code', 'is_used', 'expires_at', 'attempts', 'created_at')
    list_filter = ('login_type', 'is_used', 'created_at')
    search_fields = ('phone', 'otp_code')
    readonly_fields = ('phone', 'login_type', 'otp_code', 'expires_at', 'created_at')

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'client', 'is_active', 'created_at', 'ip_address')
    list_filter = ('role', 'client', 'is_active')
    search_fields = ('user__phone', 'jti', 'device_id')
    readonly_fields = ('user', 'role', 'client', 'jti', 'device_id', 'ip_address', 'created_at', 'revoked_at')
    actions = ['revoke_selected_sessions']

    @admin.action(description='Revoke selected sessions')
    def revoke_selected_sessions(self, request, queryset):
        for session in queryset.filter(is_active=True):
            session.revoke()
        self.message_user(request, f"{queryset.filter(is_active=False).count()} sessions revoked successfully.")

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_used', 'expires_at')
    list_filter = ('is_used',)
    search_fields = ('user__phone', 'token')