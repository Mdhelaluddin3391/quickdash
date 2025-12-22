from django.db import transaction
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from apps.utils.exceptions import BusinessLogicException

from .models import CustomerProfile, Address

class CustomerService:

    @staticmethod
    def get_or_create_profile(user):
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    @transaction.atomic
    def create_address(
        user,
        label: str,
        address_line: str,
        city: str,
        pincode: str,
        lat: float,
        lng: float,
        is_default: bool = False,
    ) -> Address:
        # 1. Lock Profile to serialize address creation for this user
        # This prevents race conditions on 'is_default' logic
        profile = (
            CustomerProfile.objects
            .select_for_update()
            .get(user=user)
        )

        # 2. Check existing addresses count
        address_count = Address.objects.filter(customer=profile).count()
        
        # 3. First address is ALWAYS default
        if address_count == 0:
            is_default = True

        # 4. If new one is default, unset others
        if is_default:
            Address.objects.filter(customer=profile, is_default=True).update(is_default=False)

        # 5. Create
        location = Point(float(lng), float(lat), srid=4326)
        
        return Address.objects.create(
            customer=profile,
            label=label,
            address_line=address_line,
            city=city,
            pincode=pincode,
            location=location,
            is_default=is_default,
        )

    @staticmethod
    @transaction.atomic
    def set_default_address(user, address_id: str):
        profile = (
            CustomerProfile.objects
            .select_for_update()
            .get(user=user)
        )

        try:
            target_address = Address.objects.get(id=address_id, customer=profile)
        except Address.DoesNotExist:
            raise ValidationError("Address not found or does not belong to user.")

        if target_address.is_default:
            return target_address

        # Unset previous default
        Address.objects.filter(customer=profile, is_default=True).update(is_default=False)

        # Set new default
        target_address.is_default = True
        target_address.save(update_fields=["is_default", "updated_at"])
        
        return target_address