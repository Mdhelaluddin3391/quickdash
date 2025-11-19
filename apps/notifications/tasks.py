# apps/notifications/tasks.py
from celery import shared_task
from apps.accounts.tasks import send_sms_task 
from .models import Notification
from .fcm import send_push_to_user # <-- New Import
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def send_order_notification(user_id, title, message):
    try:
        user = User.objects.get(id=user_id)
        
        # 1. DB mein Notification save karo (History ke liye)
        Notification.objects.create(user=user, title=title, message=message)
        
        # 2. SMS bhejo (Twilio Task)
        if user.phone:
            send_sms_task.delay(user.phone, f"{title}: {message}", "notification")
            
        # 3. Push Notification bhejo (FCM) - NEW
        # Hum async call nahi kar rahe kyunki fcm.py khud lightweight hai, 
        # par best practice ke liye ise bhi alag task bana sakte hain.
        # Abhi isi task mein call kar rahe hain simplicity ke liye.
        send_push_to_user(user.id, title, message, data={"type": "order_update"})
            
    except User.DoesNotExist:
        pass



from celery import shared_task
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import logging

# Firebase Initialize (Sirf ek baar hona chahiye)
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH) # Settings mein path hona chahiye
    firebase_admin.initialize_app(cred)

logger = logging.getLogger(__name__)

@shared_task(name="send_fcm_push_notification")
def send_fcm_push_notification_task(user_id, title, body, data=None):
    """
    User ke saare logged-in devices par notification bhejta hai.
    """
    from apps.accounts.models import User # User model import karein
    
    try:
        user = User.objects.get(id=user_id)
        # Maan rahe hain User model mein 'fcm_tokens' ya related model hai
        # Agar nahi hai, toh aapko User model mein tokens store karne honge via API
        # Example: FCMToken model
        tokens = user.fcm_tokens.values_list('token', flat=True) # List of tokens
        
        if not tokens:
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
        logger.info(f"Sent {response.success_count} messages successfully.")
        return f"Success: {response.success_count}, Failed: {response.failure_count}"

    except Exception as e:
        logger.error(f"FCM Failed: {e}")
        return str(e)