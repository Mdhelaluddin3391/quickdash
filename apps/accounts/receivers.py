from django.dispatch import receiver
from .signals import user_signed_up
from .models import CustomerProfile, RiderProfile, EmployeeProfile
import uuid

@receiver(user_signed_up)
def create_user_profile(sender, user, login_type, **kwargs):
    if login_type == 'RIDER':
        RiderProfile.objects.create(user=user, rider_code=f"RIDER-{uuid.uuid4().hex[:8].upper()}")
    elif login_type == 'EMPLOYEE':
        EmployeeProfile.objects.create(user=user, employee_code=f"EMP-{uuid.uuid4().hex[:8].upper()}", role='PICKER', warehouse_code='DEFAULT')
    else:
        CustomerProfile.objects.create(user=user)
