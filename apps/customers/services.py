from django.db import transaction
from .models import CustomerProfile, Address
from apps.utils.exceptions import BusinessLogicException

class CustomerService:
    @staticmethod
    def get_or_create_profile(user):
        profile, created = CustomerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def add_address(user, address_data):
        profile = CustomerService.get_or_create_profile(user)
        
        # If set as default, unset others
        if address_data.get('is_default'):
            Address.objects.filter(customer=profile, is_default=True).update(is_default=False)
            
        return Address.objects.create(customer=profile, **address_data)

    @staticmethod
    def update_address(user, address_id, update_data):
        profile = CustomerService.get_or_create_profile(user)
        try:
            address = Address.objects.get(id=address_id, customer=profile)
        except Address.DoesNotExist:
            raise BusinessLogicException("Address not found.")

        if update_data.get('is_default'):
            Address.objects.filter(customer=profile, is_default=True).update(is_default=False)

        for key, value in update_data.items():
            setattr(address, key, value)
        
        address.save()
        return address