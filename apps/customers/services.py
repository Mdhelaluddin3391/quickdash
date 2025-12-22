# apps/customers/services.py

from django.db import transaction
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError

from .models import CustomerProfile, Address


class CustomerService:

    @staticmethod
    def get_profile(user):
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    @transaction.atomic
    def create_address(
        user,
        label: str,
        address_line: str,
        lat: float,
        lng: float,
        is_default: bool = False,
    ) -> Address:
        profile = CustomerService.get_profile(user)

        if not Address.objects.filter(customer=profile).exists():
            is_default = True

        if is_default:
            Address.objects.filter(customer=profile, is_default=True).update(
                is_default=False
            )

        location = Point(float(lng), float(lat))  # lng, lat order

        return Address.objects.create(
            customer=profile,
            label=label,
            address_line=address_line,
            location=location,
            is_default=is_default,
        )

    @staticmethod
    @transaction.atomic
    def set_default_address(user, address_id):
        profile = CustomerService.get_profile(user)

        try:
            address = Address.objects.get(id=address_id, customer=profile)
        except Address.DoesNotExist:
            raise ValidationError("Address not found")

        Address.objects.filter(customer=profile, is_default=True).update(
            is_default=False
        )

        address.is_default = True
        address.save(update_fields=["is_default"])
        return address
