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