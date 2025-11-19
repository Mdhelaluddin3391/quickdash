# apps/notifications/fcm.py
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

logger = logging.getLogger(__name__)

# Firebase App Initialize (Singleton pattern)
if not firebase_admin._apps:
    try:
        # Production mein ye path env variable ya settings se aana chahiye
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH) 
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin Initialized.")
    except Exception as e:
        logger.warning(f"Firebase Init Failed: {e}. Push notifications will not work.")

def send_push_to_user(user_id, title, body, data=None):
    """
    User ke sabhi active devices par notification bhejne ke liye.
    """
    from .models import FCMDevice # Circular import avoid karne ke liye yahan import kiya
    
    # User ke saare tokens fetch karo
    tokens = list(FCMDevice.objects.filter(user_id=user_id, is_active=True).values_list('fcm_token', flat=True))
    
    if not tokens:
        return # Koi device nahi hai

    if data is None:
        data = {}

    # Message construct karo
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        tokens=tokens,
    )

    try:
        response = messaging.send_multicast(message)
        logger.info(f"FCM Sent: {response.success_count} successes, {response.failure_count} failures.")
        
        # Optional: Failed tokens ko cleanup kar sakte hain (agar response.failure_count > 0)
        return response
    except Exception as e:
        logger.error(f"Error sending FCM message: {e}")
        return None