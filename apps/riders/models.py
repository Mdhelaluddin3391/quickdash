from django.db import models
from django.conf import settings

class RiderStatus(models.TextChoices):
    OFFLINE = "OFFLINE", "Offline"
    ONLINE = "ONLINE", "Online"
    BUSY = "BUSY", "Busy (On Order)"

class RiderProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='rider_profile'
    )
    is_approved = models.BooleanField(default=False)
    current_status = models.CharField(
        max_length=20, 
        choices=RiderStatus.choices, 
        default=RiderStatus.OFFLINE
    )
    
    # Real-time Location Snapshot (Updated frequently via Redis/API)
    current_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    # Payout info
    earnings_wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Rider: {self.user.phone_number} [{self.current_status}]"

class Vehicle(models.Model):
    rider = models.OneToOneField(RiderProfile, on_delete=models.CASCADE, related_name='vehicle')
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=50) # Bike, Scooter, EV
    license_number = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.vehicle_type} - {self.plate_number}"