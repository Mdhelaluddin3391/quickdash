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

    # FIX: Check for App Initialization safely
    if not firebase_admin._apps:
        
        # Priority 1: Use JSON Credentials from Settings (Environment Variable)
        if hasattr(settings, 'FIREBASE_CREDENTIALS') and settings.FIREBASE_CREDENTIALS:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully (via JSON Config).")
            
        # Priority 2: Use File Path (Legacy)
        elif hasattr(settings, 'FIREBASE_CREDENTIALS_PATH') and settings.FIREBASE_CREDENTIALS_PATH:
            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized successfully (via File Path).")
            else:
                logger.warning("Firebase credentials file not found at %s.", cred_path)
        
        else:
            logger.warning("No Firebase credentials found in settings. Push notifications disabled.")
            
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