import logging
from celery import shared_task
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.core.mail import send_mail
from django.template.loader import render_to_string
# Logger setup
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)  # 3 retries, 5 min delay
def send_sms_task(self, phone: str, otp_code: str, login_type: str):
    """
    Celery task to send OTP SMS asynchronously using Twilio.
    """
    # Settings se credentials fetch karein
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_FROM_NUMBER

    if not all([account_sid, auth_token, from_number]):
        logger.error(
            "Twilio credentials missing in settings. SMS not sent to %s.", phone
        )
        return "Twilio credentials missing."

    # Twilio client initialize karein
    try:
        client = Client(account_sid, auth_token)
        
        # Message body format karein
        body = (
            f"Your OTP for QuickDash {login_type.title()} login is: {otp_code}\n"
            f"This code is valid for 5 minutes."
        )

        # Asli message send karein
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=phone  # Phone number ko +91 format mein hona chahiye
        )
        
        logger.info("Successfully sent SMS to %s, SID: %s", phone, message.sid)
        return f"SMS sent successfully to {phone} (SID: {message.sid})"

    except TwilioRestException as exc:
        # Agar koi error aaye (jaise invalid number), to log karein aur retry karein
        logger.warning(
            "Twilio error sending SMS to %s: %s. Retrying...", phone, str(exc)
        )
        # Celery ko batayein ki task retry karna hai
        self.retry(exc=exc)
        
    except Exception as exc:
        # Koi aur unexpected error
        logger.error(
            "Unexpected error sending SMS to %s: %s. Retrying...", phone, str(exc)
        )
        self.retry(exc=exc)





@shared_task(bind=True, max_retries=3, default_retry_delay=180) # 3 retries, 3 min delay
def send_admin_password_reset_email_task(self, user_email: str, user_name: str, reset_token: str):
    """
    Celery task to send Admin Password Reset email.
    """
    if not user_email:
        logger.error("No email found for user to send reset password link.")
        return "No email provided."

    try:
        # TODO: Production mein, 'reset_url' ko frontend URL se replace karein
        # Example: f"https.admin.quickdash.com/reset-password?token={reset_token}"
        reset_url = f"http://localhost:8000/api/v1/auth/admin/reset-password/?token={reset_token}" # Temporary link
        
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "token": reset_token
        }
        
        # Simple text email (aap isko HTML template se bhi render kar sakte hain)
        subject = "Your Password Reset Request for QuickDash"
        body = (
            f"Hi {user_name},\n\n"
            f"You requested a password reset. Please use the token below or click the link:\n\n"
            f"Link: {reset_url}\n"
            f"Token: {reset_token}\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"Thanks,\nQuickDash Team"
        )
        
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info("Successfully sent password reset email to %s", user_email)
        return f"Email sent to {user_email}."

    except Exception as exc:
        logger.warning(
            "Error sending password reset email to %s: %s. Retrying...", user_email, exc
        )
        self.retry(exc=exc)