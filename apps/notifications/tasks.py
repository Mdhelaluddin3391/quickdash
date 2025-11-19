# apps/notifications/tasks.py
from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings
import logging
import firebase_admin
from firebase_admin import credentials, messaging

from apps.accounts.tasks import send_sms_task 
from .models import Notification
from .fcm import send_push_to_user

User = get_user_model()
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")

@shared_task
def send_order_notification(user_id, title, message):
    try:
        user = User.objects.get(id=user_id)
        
        Notification.objects.create(user=user, title=title, message=message)
        
        if user.phone:
            send_sms_task.delay(user.phone, f"{title}: {message}", "notification")
            
        send_push_to_user(user.id, title, message, data={"type": "order_update"})
            
    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} not found. Could not send order notification.")
    except Exception as e:
        logger.error(f"An error occurred while sending order notification: {e}")

@shared_task(name="send_fcm_push_notification")
def send_fcm_push_notification_task(user_id, title, body, data=None):
    """
    Sends a push notification to all of a user's registered devices.
    """
    try:
        user = User.objects.get(id=user_id)
        tokens = user.fcm_devices.values_list('fcm_token', flat=True)
        
        if not tokens:
            logger.info(f"No FCM tokens found for user {user_id}.")
            return "No FCM tokens found for user."

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=list(tokens),
        )
        
        response = messaging.send_multicast(message)
        logger.info(f"Sent {response.success_count} push notifications to user {user_id}.")
        return f"Success: {response.success_count}, Failed: {response.failure_count}"

    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} not found. Could not send push notification.")
    except Exception as e:
        logger.error(f"FCM push notification failed for user {user_id}: {e}")
        return str(e)
