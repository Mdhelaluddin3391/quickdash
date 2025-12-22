from django.db import transaction
from django.utils import timezone
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point

from apps.utils.exceptions import BusinessLogicException
from apps.orders.models import Order
from apps.riders.models import RiderProfile # Will be finalized in Step 8
from .models import DeliveryJob
from .tasks import broadcast_delivery_update

class DeliveryService:
    
    SEARCH_RADIUS_KM = 5.0

    @staticmethod
    @transaction.atomic
    def create_delivery_job(order: Order):
        """
        Called when Warehouse DISPATCH is ready.
        """
        # Ensure Warehouse Location exists (Fallback to default if missing in Dev)
        # In Prod, warehouse always has location.
        wh_location = None
        if hasattr(order, 'warehouse') and order.warehouse.location:
            wh_location = order.warehouse.location
        else:
            # Fallback for robustness
            wh_location = Point(77.5946, 12.9716) 

        # Customer Location (From Order Snapshot)
        cust_lat = order.delivery_address.get('lat')
        cust_lng = order.delivery_address.get('lng')
        cust_location = Point(cust_lng, cust_lat)

        job = DeliveryJob.objects.create(
            order_id=order.id,
            warehouse_location=wh_location,
            customer_location=cust_location,
            status=DeliveryJob.Status.SEARCHING
        )
        
        # Trigger Async Search
        from .tasks import assign_rider_task
        assign_rider_task.delay(str(job.id))
        
        return job

    @staticmethod
    @transaction.atomic
    def assign_nearest_rider(job_id: str):
        """
        Finds nearest available rider and assigns job.
        """
        job = DeliveryJob.objects.select_for_update().get(id=job_id)
        
        if job.status != DeliveryJob.Status.SEARCHING:
            return # Already assigned or cancelled

        # Geospatial Query: Find riders within 5km, ordered by distance
        # We filter for: 
        # 1. Active status
        # 2. Available state
        # 3. Last location update recent (handled in Rider Service usually)
        
        candidates = RiderProfile.objects.filter(
            is_available=True,
            current_location__distance_lte=(job.warehouse_location, D(km=DeliveryService.SEARCH_RADIUS_KM))
        ).annotate(
            distance=Distance('current_location', job.warehouse_location)
        ).order_by('distance')

        rider_profile = candidates.first()

        if rider_profile:
            # Assign
            job.rider = rider_profile.user
            job.status = DeliveryJob.Status.ASSIGNED
            job.save()

            # Mark Rider Busy (Step 8 will enforce this model logic)
            rider_profile.is_available = False
            rider_profile.save()

            # Notify Rider (WebSocket)
            broadcast_delivery_update(str(job.id), "ASSIGNED", {"rider_id": str(job.rider.id)})
            return True
        else:
            # Retry later?
            return False

    @staticmethod
    @transaction.atomic
    def update_job_status(job_id: str, status: str, user):
        job = DeliveryJob.objects.select_for_update().get(id=job_id)
        
        if job.rider != user:
            raise BusinessLogicException("Not authorized for this job.")

        job.status = status
        
        if status == DeliveryJob.Status.PICKED_UP:
            job.pickup_time = timezone.now()
            # Notify Customer
            
        elif status == DeliveryJob.Status.COMPLETED:
            job.completion_time = timezone.now()
            # Mark Rider Available again
            from apps.riders.services import RiderService
            RiderService.mark_available(user)
            
            # Update Order Status
            Order.objects.filter(id=job.order_id).update(status=Order.Status.DELIVERED)

        job.save()
        broadcast_delivery_update(str(job.id), status, {})
        return job