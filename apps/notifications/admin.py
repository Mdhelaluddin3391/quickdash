# apps/notifications/admin.py
from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'is_read', 'sent_at')
    list_filter = ('is_read', 'sent_at')
    search_fields = ('user__phone', 'title', 'message')
    date_hierarchy = 'sent_at'
    
    # Notifications ko admin se edit/add nahi karna hai
    readonly_fields = ('user', 'title', 'message', 'sent_at')
    
    def has_add_permission(self, request):
        return False