# apps/notifications/models.py
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.utils.models import TimestampedModel


class NotificationChannel(models.TextChoices):
    PUSH = "push", "Push"
    SMS = "sms", "SMS"
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"
    IN_APP = "in_app", "In App"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class NotificationTemplate(TimestampedModel):
    """
    Template for a notification type.

    Example key:
    - order_created_customer
    - order_out_for_delivery
    - delivery_completed_customer
    - rider_assigned_dispatch
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True, db_index=True)

    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.PUSH,
    )

    title_template = models.CharField(max_length=255, blank=True)
    body_template = models.TextField()

    is_active = models.BooleanField(default=True)

    default_priority = models.IntegerField(
        default=5,
        help_text="1 = highest, 10 = lowest",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"[{self.channel}] {self.key}"


class UserNotificationPreference(TimestampedModel):
    """
    Simple per-user notification preferences.
    (Can be extended to per-event basis later.)
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_pref",
    )

    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"NotificationPref({self.user_id})"


class Notification(TimestampedModel):
    """
    Single notification instance (inbox row).

    - Created whenever we decide to notify a user.
    - Then Celery task sends via appropriate channel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    template = models.ForeignKey(
        NotificationTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.PUSH,
    )

    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()

    data = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True,
    )

    error_message = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["channel"]),
        ]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def __str__(self):
        return f"{self.user_id} [{self.channel}] {self.title or self.template_id}"


class FCMDevice(TimestampedModel):
    """
    Device token for Firebase Cloud Messaging (Push Notifications).
    """

    ANDROID = "android"
    IOS = "ios"
    WEB = "web"

    DEVICE_TYPE_CHOICES = [
        (ANDROID, "Android"),
        (IOS, "iOS"),
        (WEB, "Web"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
    )
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_TYPE_CHOICES,
        default=ANDROID,
    )
    is_active = models.BooleanField(default=True)

    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.device_type}"
