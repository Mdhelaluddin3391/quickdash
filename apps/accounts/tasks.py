from celery import shared_task
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_sms_task(phone: str, code: str, role: str):
    """
    Async task to send SMS.
    In production, integrate with Twilio/SNS here.
    """
    message = f"Your {settings.PROJECT_NAME} verification code for {role} is: {code}"
    
    # TODO: Replace with actual SMS Provider SDK
    # client.messages.create(body=message, from_=..., to=phone)
    
    # For Development: Log it so you can see it in the console
    logger.info(f"==> SMS SENT to {phone}: {message}")
    return f"SMS sent to {phone}"