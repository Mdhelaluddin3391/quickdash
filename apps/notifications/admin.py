# apps/notifications/admin.py
from django.contrib import admin

from .models import (
    NotificationTemplate,
    Notification,
    FCMDevice,
    UserNotificationPreference,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "channel", "is_active", "default_priority")
    search_fields = ("key", "title_template", "body_template")
    list_filter = ("channel", "is_active")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "channel",
        "title",
        "status",
        "is_read",
        "created_at",
        "sent_at",
    )
    list_filter = ("channel", "status", "is_read")
    search_fields = ("title", "body", "user__phone")
    readonly_fields = (
        "user",
        "template",
        "channel",
        "title",
        "body",
        "data",
        "status",
        "provider_message_id",
        "error_message",
        "sent_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "device_type", "is_active", "last_seen_at")
    list_filter = ("device_type", "is_active")
    search_fields = ("user__phone", "token")


@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "push_enabled", "sms_enabled", "email_enabled", "whatsapp_enabled")
    search_fields = ("user__phone",)
