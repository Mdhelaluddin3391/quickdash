from django.dispatch import receiver
from .signals import user_signed_up
from .models import CustomerProfile
# RiderProfile, EmployeeProfile ab yahan se auto-create NHI karenge
# Onboarding / HR APIs handle karenge.


@receiver(user_signed_up)
def create_user_profile(sender, user, login_type, **kwargs):
    """
    Ab yeh signal sirf CUSTOMER ke liye profile banata hai.

    - CUSTOMER → CustomerProfile auto
    - RIDER / EMPLOYEE → Onboarding / HR APIs se create honge,
      OTP se auto-creation bilkul nahi.
    """
    if login_type == 'CUSTOMER':
        CustomerProfile.objects.get_or_create(user=user)
