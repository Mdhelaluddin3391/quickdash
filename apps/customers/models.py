# apps/customers/models.py

import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.conf import settings


class CustomerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CustomerProfile({self.user.phone})"


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    label = models.CharField(max_length=50)  # Home, Work, etc
    address_line = models.TextField()

    # ✅ SINGLE SOURCE OF TRUTH FOR GEO
    location = gis_models.PointField(geography=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        indexes = [
            gis_models.Index(fields=["location"]),
        ]

    def __str__(self):
        return f"{self.label} - {self.customer.user.phone}"

    def as_dict(self):
        """
        Snapshot-safe representation for Orders
        """
        return {
            "id": str(self.id),
            "label": self.label,
            "address_line": self.address_line,
            "lat": self.location.y,
            "lng": self.location.x,
        }
