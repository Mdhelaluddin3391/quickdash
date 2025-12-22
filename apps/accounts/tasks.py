from celery import shared_task
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger("django")

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_sms_task(self, phone: str, code: str, role: str):
    """
    Sends OTP via Twilio.
    Retries on network failure.
    """
    message_body = f"Your QuickDash verification code is: {code}. Do not share this with anyone."
    
    try:
        # Fail fast if config missing in Prod
        if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER]):
            if settings.DEBUG:
                logger.warning("Twilio credentials missing. Skipping SMS.")
                return "Skipped (Config Missing)"
            raise ValueError("Twilio configuration missing in Production!")

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=phone
        )
        logger.info(f"SMS sent to {phone}. SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        logger.error(f"Twilio Error: {e}")
        # Only retry server errors, not bad request (invalid number)
        if 500 <= e.status < 600:
            raise self.retry(exc=e)
        return f"Failed: {e}"
    except Exception as e:
        logger.exception(f"Unknown SMS Error: {e}")
        raise self.retry(exc=e)