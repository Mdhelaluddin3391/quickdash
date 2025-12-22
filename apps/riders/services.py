from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction

from .models import RiderProfile, RiderStatus
from apps.utils.exceptions import BusinessLogicException, NotFound

class RiderService:
    """
    Handles Rider Lifecycle: Profile, Status, Location updates.
    """
    
    @staticmethod
    def get_profile(user):
        try:
            return user.rider_profile
        except RiderProfile.DoesNotExist:
            raise NotFound("Rider profile does not exist.")

    @staticmethod
    def create_pending_profile(user):
        """
        Idempotent creation of a pending profile.
        """
        profile, created = RiderProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def toggle_status(user, status):
        profile = RiderService.get_profile(user)
        
        if not profile.is_approved:
            raise BusinessLogicException("Rider account is not yet approved.")
            
        if status not in RiderStatus.values:
            raise BusinessLogicException(f"Invalid status: {status}")
            
        profile.current_status = status
        profile.save(update_fields=['current_status', 'updated_at'])
        return profile

    @staticmethod
    def update_location(user, lat: float, lng: float):
        """
        Updates rider location. 
        Note: In hyper-scale, this writes to Redis. Here we write to DB (PostGIS).
        """
        profile = RiderService.get_profile(user)
        
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise BusinessLogicException("Invalid coordinates.")

        profile.current_location = Point(lng, lat, srid=4326)
        profile.last_location_update = timezone.now()
        
        # Auto-switch to ONLINE if they were OFFLINE? (Business decision: optional)
        # if profile.current_status == RiderStatus.OFFLINE:
        #     profile.current_status = RiderStatus.ONLINE
            
        profile.save(update_fields=['current_location', 'last_location_update'])
        return profile


class RiderAssignmentService:
    """
    Domain Service for finding and reserving riders.
    Used by Dispatch/Order systems.
    """

    @staticmethod
    def find_eligible_riders_nearby(lat: float, lng: float, radius_km: float = 5.0, limit: int = 5):
        """
        Finds riders who are:
        1. ONLINE
        2. APPROVED
        3. Within radius
        """
        target_location = Point(lng, lat, srid=4326)
        
        # Spatial Query using PostGIS
        riders = RiderProfile.objects.filter(
            current_status=RiderStatus.ONLINE,
            is_approved=True,
            current_location__distance_lte=(target_location, D(km=radius_km))
        ).annotate(
            distance=Distance('current_location', target_location)
        ).order_by('distance')[:limit]
        
        return riders

    @staticmethod
    def check_rider_availability(rider_id: str) -> bool:
        """
        Atomic check if a specific rider is still available.
        """
        try:
            rider = RiderProfile.objects.get(id=rider_id)
            return (
                rider.current_status == RiderStatus.ONLINE and 
                rider.is_approved
            )
        except RiderProfile.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def mark_rider_busy(rider: RiderProfile):
        """
         locks the rider row to prevent double assignment.
        """
        rider = RiderProfile.objects.select_for_update().get(id=rider.id)
        if rider.current_status != RiderStatus.ONLINE:
            raise BusinessLogicException("Rider is not available.")
        
        rider.current_status = RiderStatus.BUSY
        rider.save(update_fields=['current_status'])
        return rider

    @staticmethod
    @transaction.atomic
    def release_rider(rider: RiderProfile):
        rider = RiderProfile.objects.select_for_update().get(id=rider.id)
        rider.current_status = RiderStatus.ONLINE
        rider.save(update_fields=['current_status'])
        return rider