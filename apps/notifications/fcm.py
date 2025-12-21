# apps/notifications/fcm.py
import logging
import os
from django.conf import settings
from .models import FCMDevice

logger = logging.getLogger(__name__)

messaging = None

try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    # FIX: Initialize Firebase App if not already initialized
    if not firebase_admin._apps:
        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully.")
        else:
            logger.warning("Firebase credentials not found at %s. Push notifications disabled.", cred_path)
            messaging = None
            
except ImportError:
    logger.warning("firebase_admin library not installed.")
    messaging = None
except Exception as e:
    logger.error(f"Error initializing Firebase: {e}")
    messaging = None


def send_push_to_device(device: FCMDevice, title: str, body: str, data: dict | None = None) -> str | None:
    """
    Fire a single push notification to given device.
    Returns provider message id or None.
    """
    if messaging is None:
        logger.debug("Skipping push: Firebase not configured.")
        return None

    if not device.is_active:
        logger.info("Skipping push to inactive device %s", device.id)
        return None

    data = data or {}

    try:
        # Construct Message
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
        
        # Send
        response = messaging.send(message)
        logger.info("FCM push sent to %s: %s", device.token, response)
        return response

    except Exception as exc:
        logger.exception("Failed to send FCM push to %s: %s", device.token, exc)
        return None