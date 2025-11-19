import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import User, CustomerProfile, RiderProfile, EmployeeProfile, PhoneOTP

logger = logging.getLogger(__name__)

# ==========================================
# 1. User & Profile Management Signals
# ==========================================

@receiver(post_save, sender=User)
def manage_user_profiles(sender, instance, created, **kwargs):
    """
    Yeh ek 'Master Signal' hai jo User create/update hone par run hota hai.
    Yeh check karta hai ki user ke paas kaunse flags (is_rider, etc) hain
    aur us hisaab se missing profiles create karta hai.
    """
    if created:
        logger.info(f"New User Registered: {instance.phone}")
        # Default: Har user Customer toh hota hi hai
        if not hasattr(instance, 'customer_profile'):
            CustomerProfile.objects.create(user=instance)
            logger.info(f"--> Created CustomerProfile for {instance.phone}")

    # --- Dynamic Profile Creation (Update hone par bhi chalega) ---
    
    # 1. Rider Logic
    if instance.is_rider and not hasattr(instance, 'rider_profile'):
        # Rider code generate karne ka simple logic (UUID ya Phone se)
        rider_code = f"R-{instance.phone[-4:]}" 
        RiderProfile.objects.create(user=instance, rider_code=rider_code)
        logger.info(f"--> Created RiderProfile for {instance.phone} (Code: {rider_code})")

    # 2. Employee Logic
    if instance.is_employee and not hasattr(instance, 'employee_profile'):
        # Default values ke saath profile banayenge, baad mein Admin update karega
        emp_code = f"EMP-{instance.phone[-4:]}"
        EmployeeProfile.objects.create(
            user=instance, 
            employee_code=emp_code,
            role="PICKER", # Default Role
            warehouse_code="WH-DEFAULT"
        )
        logger.info(f"--> Created EmployeeProfile for {instance.phone}")


# ==========================================
# 2. OTP & Notification Signals
# ==========================================

@receiver(post_save, sender=PhoneOTP)
def send_otp_sms(sender, instance, created, **kwargs):
    """
    Jaise hi PhoneOTP table mein nayi row banti hai, yeh signal trigger hota hai.
    Hum yahan se SMS provider (Twilio/Msg91) ko call karte hain.
    
    Faida: Views mein 'send_sms()' likhne ki zaroorat nahi.
    """
    if created:
        # Yahan hum actual SMS logic likhenge (ya Celery task call karenge)
        message = f"Your QuickDash OTP is {instance.otp_code}. Valid for 5 mins."
        
        # Simulation (Console mein print hoga)
        print(f"\n[SMS SERVICE] Sending SMS to {instance.phone}: {message}\n")
        
        # Real world mein hum yahaan Celery Task call karte hain:
        # send_sms_task.delay(instance.phone, message)