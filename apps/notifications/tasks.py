import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from .models import Notification, NotificationChannel, NotificationStatus, FCMDevice
from .fcm import send_push_to_device

logger = logging.getLogger(__name__)

def _send_push_notification(notification: Notification) -> str | None:
    """
    Push via FCM to all active devices of user.
    """
    devices = FCMDevice.objects.filter(user=notification.user, is_active=True)
    if not devices.exists():
        return None

    last_response = None
    for dev in devices:
        resp = send_push_to_device(
            device=dev,
            title=notification.title,
            body=notification.body,
            data=notification.data,
        )
        if resp:
            last_response = resp
    return last_response

def _send_sms_notification(notification: Notification) -> str | None:
    """
    Sends actual SMS using Twilio credentials from settings.
    """
    user = notification.user
    phone = getattr(user, "phone", None)
    
    if not phone:
        logger.warning(f"Cannot send SMS: User {user.id} has no phone number.")
        return None

    # Twilio Credentials Check
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_FROM_NUMBER

    if not all([account_sid, auth_token, from_number]):
        logger.error("Twilio credentials missing in settings. SMS not sent.")
        return None

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=notification.body,
            from_=from_number,
            to=phone
        )
        logger.info(f"SMS sent to {phone}. SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        logger.error(f"Twilio Error sending SMS to {phone}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error sending SMS: {e}")
        return None

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_notification_task(self, notification_id: str):
    try:
        with transaction.atomic():
            # Lock the row to prevent race conditions
            notification = Notification.objects.select_for_update().get(id=notification_id)

            if notification.status == NotificationStatus.SENT:
                return

            provider_id = None
            if notification.channel == NotificationChannel.PUSH:
                provider_id = _send_push_notification(notification)
            elif notification.channel == NotificationChannel.SMS:
                provider_id = _send_sms_notification(notification)
            else:
                logger.info(f"Channel {notification.channel} not implemented yet.")

            # Update status
            notification.provider_message_id = provider_id or ""
            notification.status = NotificationStatus.SENT if provider_id else NotificationStatus.FAILED
            notification.sent_at = timezone.now()
            notification.save(update_fields=["provider_message_id", "status", "sent_at"])

    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found.")
    except Exception as exc:
        logger.exception(f"Failed to send notification {notification_id}")
        self.retry(exc=exc)