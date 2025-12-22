from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import CustomerProfile, Address
from apps.utils.exceptions import BusinessLogicException, NotFound

class CustomerService:
    @staticmethod
    def get_or_create_profile(user):
        """
        Retrieves the customer profile for a given user, creating it if necessary.
        """
        profile, created = CustomerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_default_address(user):
        """
        Returns the default address for the user, or None.
        """
        profile = CustomerService.get_or_create_profile(user)
        return profile.addresses.filter(is_default=True).first()

    @staticmethod
    def add_address(user, address_data):
        """
        Adds a new address. If marked as default, unsets previous defaults.
        """
        profile = CustomerService.get_or_create_profile(user)
        
        with transaction.atomic():
            if address_data.get('is_default'):
                Address.objects.filter(customer=profile, is_default=True).update(is_default=False)
            
            # If this is the FIRST address, force it to be default
            if not Address.objects.filter(customer=profile).exists():
                address_data['is_default'] = True

            return Address.objects.create(customer=profile, **address_data)

    @staticmethod
    def update_address(user, address_id, update_data):
        """
        Updates an address safely.
        """
        profile = CustomerService.get_or_create_profile(user)
        try:
            address = Address.objects.get(id=address_id, customer=profile)
        except Address.DoesNotExist:
            raise NotFound("Address not found or does not belong to this user.")

        with transaction.atomic():
            if update_data.get('is_default'):
                Address.objects.filter(customer=profile, is_default=True).update(is_default=False)

            for key, value in update_data.items():
                setattr(address, key, value)
            
            address.save()
            return address

    @staticmethod
    def delete_address(user, address_id):
        profile = CustomerService.get_or_create_profile(user)
        deleted_count, _ = Address.objects.filter(id=address_id, customer=profile).delete()
        if deleted_count == 0:
            raise NotFound("Address not found.")