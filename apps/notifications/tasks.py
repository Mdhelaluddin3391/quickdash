from celery import shared_task
from apps.accounts.tasks import send_sms_task # Reuse existing SMS task
from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def send_order_notification(user_id, title, message):
    try:
        user = User.objects.get(id=user_id)
        # 1. DB mein save karo
        Notification.objects.create(user=user, title=title, message=message)
        
        # 2. SMS bhejo (Agar phone number hai)
        if user.phone:
            send_sms_task.delay(user.phone, f"{title}: {message}", "notification")
            
    except User.DoesNotExist:
        pass