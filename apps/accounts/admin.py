from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['phone']
    list_display = ['phone', 'full_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['phone', 'full_name', 'email']
    
    # Since we use phone as username, we adjust fieldsets
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('full_name', 'email', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'role'),
        }),
    )

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['phone', 'code', 'role', 'is_verified', 'created_at', 'expires_at']
    list_filter = ['is_verified', 'role', 'created_at']
    search_fields = ['phone']
    readonly_fields = ['created_at']