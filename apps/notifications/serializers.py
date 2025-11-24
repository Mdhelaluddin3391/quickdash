# apps/notifications/serializers.py
from rest_framework import serializers

from .models import Notification, FCMDevice, NotificationTemplate


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "channel",
            "title",
            "body",
            "data",
            "status",
            "is_read",
            "read_at",
            "created_at",
            "sent_at",
        ]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "key",
            "channel",
            "title_template",
            "body_template",
            "is_active",
            "default_priority",
            "metadata",
            "created_at",
            "updated_at",
        ]


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ["id", "token", "device_type", "is_active", "last_seen_at"]
        read_only_fields = ["last_seen_at"]
