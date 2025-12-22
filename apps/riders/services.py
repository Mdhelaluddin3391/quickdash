from django.contrib.gis.geos import Point
from django.utils import timezone
from django.db import transaction
from .models import RiderProfile, RiderEarnings
from .models import RiderShift

class RiderService:

    @staticmethod
    @transaction.atomic
    def toggle_status(user, is_online: bool):
        """
        Rider switches "Start Duty" / "Stop Duty".
        Manages Shift Records automatically.
        """
        profile = user.rider_profile
        
        # No change? Exit
        if profile.is_online == is_online:
            return profile

        now = timezone.now()

        if is_online:
            # START SHIFT
            profile.is_online = True
            profile.is_available = True
            
            # Create new shift record
            RiderShift.objects.create(
                rider=profile,
                start_time=now,
                status="ACTIVE"
            )
        else:
            # END SHIFT
            profile.is_online = False
            profile.is_available = False
            
            # Close active shift
            active_shift = RiderShift.objects.filter(
                rider=profile, 
                end_time__isnull=True
            ).last()
            
            if active_shift:
                active_shift.end_time = now
                active_shift.duration_minutes = (now - active_shift.start_time).seconds // 60
                active_shift.status = "COMPLETED"
                active_shift.save()

        profile.save(update_fields=['is_online', 'is_available'])
        return profile

    @staticmethod
    def create_pending_profile(user):
        return RiderProfile.objects.get_or_create(user=user)

    @staticmethod
    def update_location(user, lat: float, lng: float):
        """
        High-frequency update from Rider App.
        """
        profile = user.rider_profile
        profile.current_location = Point(float(lng), float(lat), srid=4326)
        profile.last_heartbeat = timezone.now()
        
        # Auto-set offline if no heartbeat for X mins? (Handled by periodic task usually)
        # For now, just update.
        profile.save(update_fields=['current_location', 'last_heartbeat'])
        
        return profile

    @staticmethod
    def toggle_status(user, is_online: bool):
        """
        Rider switches "Start Duty" / "Stop Duty".
        """
        profile = user.rider_profile
        profile.is_online = is_online
        
        # If going offline, remove availability
        if not is_online:
            profile.is_available = False
        else:
            # If going online, they are available unless they have an active job
            # (Check active jobs logic could be here, but simpler: start as available)
            profile.is_available = True
            
        profile.save(update_fields=['is_online', 'is_available'])
        return profile

    @staticmethod
    def mark_busy(user):
        """Called when a job is assigned"""
        RiderProfile.objects.filter(user=user).update(is_available=False)

    @staticmethod
    def mark_available(user):
        """Called when a job is completed"""
        # Only mark available if they are still "Online"
        profile = user.rider_profile
        if profile.is_online:
            profile.is_available = True
            profile.save(update_fields=['is_available'])

    @staticmethod
    def credit_earnings(user, order_id: str, amount: float):
        """
        Called by Delivery Service upon job completion.
        """
        profile = user.rider_profile
        RiderEarnings.objects.create(
            rider=profile,
            order_id=order_id,
            amount=amount,
            description=f"Delivery payout for {order_id}"
        )
        
        # Update metrics
        profile.total_deliveries += 1
        profile.save(update_fields=['total_deliveries'])