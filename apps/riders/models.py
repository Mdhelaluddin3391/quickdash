from django.contrib.gis.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.utils.models import TimestampedModel

class RiderStatus(models.TextChoices):
    OFFLINE = "OFFLINE", _("Offline")
    ONLINE = "ONLINE", _("Online")
    BUSY = "BUSY", _("Busy (On Order)")

class RiderProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='rider_profile'
    )
    is_approved = models.BooleanField(default=False)
    
    # Operational State
    current_status = models.CharField(
        max_length=20, 
        choices=RiderStatus.choices, 
        default=RiderStatus.OFFLINE,
        db_index=True
    )
    
    # Geospatial Location (SRID 4326 for GPS Lat/Lng)
    current_location = models.PointField(null=True, blank=True, srid=4326)
    last_location_update = models.DateTimeField(null=True, blank=True)

    # Financials
    earnings_wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Rider Profile"
        verbose_name_plural = "Rider Profiles"
        indexes = [
            models.Index(fields=['current_status', 'is_approved']),
        ]

    def __str__(self):
        return f"{self.user.phone} [{self.current_status}]"

class Vehicle(TimestampedModel):
    class VehicleType(models.TextChoices):
        BIKE = "BIKE", _("Bike")
        SCOOTER = "SCOOTER", _("Scooter")
        EV = "EV", _("Electric Vehicle")
        BICYCLE = "BICYCLE", _("Bicycle")

    rider = models.OneToOneField(RiderProfile, on_delete=models.CASCADE, related_name='vehicle')
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=50, choices=VehicleType.choices, default=VehicleType.BIKE)
    license_number = models.CharField(max_length=50)
    
    # Metadata for vehicle specifics (Model, Year, Color)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.vehicle_type} - {self.plate_number}"