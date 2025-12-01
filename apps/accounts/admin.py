# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, CustomerProfile, RiderProfile, EmployeeProfile,
    PhoneOTP, UserSession, PasswordResetToken, Address
)

# --- Inlines ---
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

# --- Main User Admin ---
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'full_name', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('phone', 'email', 'full_name')
    ordering = ('phone',)
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('email', 'full_name', 'app_role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'fields': ('phone', 'password')}),
    )
    inlines = [CustomerProfileInline, RiderProfileInline, EmployeeProfileInline, AddressInline]

# --- Address Admin ---
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'address_type', 'city', 'pincode', 'is_default')
    list_filter = ('address_type', 'is_default')
    search_fields = ('user__phone', 'full_address', 'pincode')
    raw_id_fields = ('user',)

# --- Other Admins ---
@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'login_type', 'otp_code', 'is_used', 'expires_at')
    list_filter = ('login_type', 'is_used')
    search_fields = ('phone',)

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'client', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__phone',)

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_used', 'expires_at')