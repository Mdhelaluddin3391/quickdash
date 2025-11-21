# apps/notifications/tasks.py
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Notification, NotificationChannel, NotificationStatus, FCMDevice
from .fcm import send_push_to_device

logger = logging.getLogger(__name__)


def _send_push_notification(notification: Notification) -> str | None:
    """
    Push via FCM to all active devices of user.
    """
    devices = FCMDevice.objects.filter(
        user=notification.user,
        is_active=True,
    )

    if not devices.exists():
        logger.info("No active FCM devices for user %s", notification.user_id)
        return None

    last_response = None

    for dev in devices:
        resp = send_push_to_device(
            device=dev,
            title=notification.title,
            body=notification.body,
            data=notification.data,
        )
        last_response = resp

        if resp is None:
            # if token invalid, optionally deactivate
            # dev.is_active = False
            # dev.save(update_fields=["is_active"])
            pass

    return last_response


def _send_sms_notification(notification: Notification) -> str | None:
    """
    Dummy SMS sender – integrate with real SMS provider here.
    """
    user = notification.user
    phone = getattr(user, "phone", None)
    if not phone:
        logger.warning(
            "Cannot send SMS notification %s – user %s has no phone.",
            notification.id,
            user.id,
        )
        return None

    logger.info(
        "SMS to %s: %s",
        phone,
        notification.body,
    )
    # TODO: integrate with SMS provider (Exotel/Twilio/etc.)
    return "sms-mock-id"


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_notification_task(self, notification_id: str):
    """
    Sends a single Notification instance via its channel.
    """
    try:
        with transaction.atomic():
            notification = (
                Notification.objects.select_for_update().get(id=notification_id)
            )

            if notification.status == NotificationStatus.SENT:
                logger.info("Notification %s already sent, skipping", notification_id)
                return

            if notification.channel == NotificationChannel.PUSH:
                provider_id = _send_push_notification(notification)

            elif notification.channel == NotificationChannel.SMS:
                provider_id = _send_sms_notification(notification)

            else:
                # For now we treat email/whatsapp as not implemented
                logger.info(
                    "Channel %s not implemented for notification %s",
                    notification.channel,
                    notification.id,
                )
                provider_id = None

            notification.provider_message_id = provider_id or ""
            notification.status = NotificationStatus.SENT
            notification.sent_at = timezone.now()
            notification.error_message = ""
            notification.save(
                update_fields=[
                    "provider_message_id",
                    "status",
                    "sent_at",
                    "error_message",
                ]
            )

    except Notification.DoesNotExist:
        logger.error("Notification %s does not exist", notification_id)
        return

    except Exception as exc:
        logger.exception(
            "Failed to send notification %s: %s", notification_id, exc
        )
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(exc)
            notification.save(update_fields=["status", "error_message"])
        except Notification.DoesNotExist:
            pass
        raise self.retry(exc=exc)
