# apps/notifications/fcm.py
import logging

from django.conf import settings

from .models import FCMDevice

logger = logging.getLogger(__name__)

try:
    # If firebase_admin is installed and configured
    from firebase_admin import messaging
except Exception:  # pragma: no cover
    messaging = None
    logger.warning("firebase_admin not available, FCM push disabled.")


def send_push_to_device(device: FCMDevice, title: str, body: str, data: dict | None = None) -> str | None:
    """
    Fire a single push notification to given device.
    Returns provider message id or None.
    """
    if messaging is None:
        logger.info("Skipping push, firebase_admin not configured.")
        return None

    if not device.is_active:
        logger.info("Skipping push to inactive device %s", device.id)
        return None

    data = data or {}

    try:
        message = messaging.Message(
            token=device.token,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={k: str(v) for k, v in data.items()},
            android=messaging.AndroidConfig(
                priority="high",
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
            ),
        )
        response = messaging.send(message)
        logger.info("FCM push sent to %s: %s", device.token, response)
        return response
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to send FCM push to %s: %s", device.token, exc)
        return None
