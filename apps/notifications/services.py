# apps/notifications/services.py
import logging
from string import Template

from django.conf import settings
from django.utils import timezone

from .models import (
    NotificationTemplate,
    Notification,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreference,
)

logger = logging.getLogger(__name__)


def _render_template(template: NotificationTemplate, context: dict | None) -> tuple[str, str]:
    """
    Safely render title/body using ${var} placeholders.
    """
    context = context or {}
    title = template.title_template or ""
    body = template.body_template or ""

    try:
        title = Template(title).safe_substitute(**context)
        body = Template(body).safe_substitute(**context)
    except Exception:
        logger.exception("Failed to render template %s", template.key)
    return title, body


def get_or_create_default_template(key: str, channel: str, title: str, body: str) -> NotificationTemplate:
    """
    Convenience: ensures template exists for a given key.
    Useful while evolving system.
    """
    template, created = NotificationTemplate.objects.get_or_create(
        key=key,
        defaults={
            "channel": channel,
            "title_template": title,
            "body_template": body,
            "is_active": True,
        },
    )
    return template


def _is_channel_enabled_for_user(user, channel: str) -> bool:
    """
    Check global channel preference for user.
    """
    try:
        pref = user.notification_pref
    except UserNotificationPreference.DoesNotExist:
        # default: push+sms enabled, others off
        if channel in (NotificationChannel.PUSH, NotificationChannel.SMS):
            return True
        return False

    mapping = {
        NotificationChannel.PUSH: pref.push_enabled,
        NotificationChannel.SMS: pref.sms_enabled,
        NotificationChannel.EMAIL: pref.email_enabled,
        NotificationChannel.WHATSAPP: pref.whatsapp_enabled,
        NotificationChannel.IN_APP: True,
    }
    return mapping.get(channel, False)


def notify_user(
    user,
    event_key: str,
    context: dict | None = None,
    *,
    channel: str | None = None,
    extra_data: dict | None = None,
    template_fallback_title: str = "",
    template_fallback_body: str = "",
) -> Notification | None:
    """
    Main entry point for other apps.

    Example usage:
        notify_user(
            user=order.customer,
            event_key="order_created_customer",
            context={"order_id": str(order.id), "amount": str(order.final_amount)},
        )

    Steps:
    - Resolve template by event_key.
    - Decide channel:
        - If explicit `channel` given -> use that.
        - Else use template.channel.
    - Check user preference for that channel.
    - Create Notification row (status = pending).
    - Schedule Celery task to send (send_notification_task).
    """
    from .tasks import send_notification_task

    if not user:
        return None

    template = NotificationTemplate.objects.filter(key=event_key, is_active=True).first()
    if not template:
        # create a minimal one so system keeps working
        template = get_or_create_default_template(
            key=event_key,
            channel=channel or NotificationChannel.PUSH,
            title=template_fallback_title,
            body=template_fallback_body or event_key,
        )

    used_channel = channel or template.channel

    if not _is_channel_enabled_for_user(user, used_channel):
        logger.info(
            "Notification for user=%s, event=%s skipped (channel %s disabled)",
            user.id,
            event_key,
            used_channel,
        )
        return None

    title, body = _render_template(template, context or {})
    data = extra_data or {}

    notification = Notification.objects.create(
        user=user,
        template=template,
        channel=used_channel,
        title=title,
        body=body,
        data=data,
        status=NotificationStatus.PENDING,
    )

    # async send
    send_notification_task.delay(str(notification.id))

    return notification
