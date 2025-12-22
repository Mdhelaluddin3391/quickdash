from django.utils import timezone
from .models import RiderProfile, RiderStatus
from apps.utils.exceptions import BusinessLogicException

class RiderService:
    @staticmethod
    def get_profile(user):
        try:
            return user.rider_profile
        except RiderProfile.DoesNotExist:
            raise BusinessLogicException("Rider profile not found.")

    @staticmethod
    def toggle_status(user, status):
        profile = RiderService.get_profile(user)
        
        if not profile.is_approved:
            raise BusinessLogicException("Rider account is not approved yet.")
            
        if status not in RiderStatus.values:
            raise BusinessLogicException("Invalid status.")
            
        profile.current_status = status
        profile.save()
        return profile

    @staticmethod
    def update_location(user, lat, lng):
        """
        Updates the rider's last known location. 
        In a real High-Scale system, this would write to Redis (Geo) directly.
        For V2 Modular Monolith, we update DB but assume high-frequency updates 
        might be throttled or sent to a separate service.
        """
        profile = RiderService.get_profile(user)
        profile.current_lat = lat
        profile.current_lng = lng
        profile.last_location_update = timezone.now()
        profile.save(update_fields=['current_lat', 'current_lng', 'last_location_update'])