from django.db import transaction
from django.utils import timezone
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from apps.utils.exceptions import BusinessLogicException
from apps.orders.models import Order
from apps.riders.models import RiderProfile
from .models import DeliveryJob
from .tasks import broadcast_delivery_update

class DeliveryService:
    SEARCH_RADIUS_KM = 5.0

    @staticmethod
    @transaction.atomic
    def create_delivery_job(order: Order):
        wh_location = order.warehouse.location if hasattr(order, 'warehouse') and order.warehouse.location else Point(77.5946, 12.9716)
        
        # Safe access to dict
        addr = order.delivery_address if isinstance(order.delivery_address, dict) else {}
        cust_lat = addr.get('lat', 12.9716)
        cust_lng = addr.get('lng', 77.5946)
        
        job = DeliveryJob.objects.create(
            order_id=order.id,
            warehouse_location=wh_location,
            customer_location=Point(float(cust_lng), float(cust_lat)),
            status=DeliveryJob.Status.SEARCHING
        )
        
        from .tasks import assign_rider_task
        assign_rider_task.delay(str(job.id))
        return job

    @staticmethod
    @transaction.atomic
    def assign_nearest_rider(job_id: str):
        job = DeliveryJob.objects.select_for_update().get(id=job_id)
        
        if job.status != DeliveryJob.Status.SEARCHING:
            return False

        # 1. Find candidates (Fast Read)
        candidates = RiderProfile.objects.filter(
            is_available=True,
            is_online=True,
            current_location__distance_lte=(job.warehouse_location, D(km=DeliveryService.SEARCH_RADIUS_KM))
        ).annotate(
            distance=Distance('current_location', job.warehouse_location)
        ).order_by('distance').values_list('id', flat=True)[:5]

        # 2. Lock & Assign (Fail Fast Strategy)
        for rider_id in candidates:
            try:
                # [CRITICAL FIX] Lock the rider row. SKIP_LOCKED prevents waiting.
                rider = RiderProfile.objects.select_for_update(skip_locked=True).get(id=rider_id, is_available=True)
                
                # Assign
                job.rider = rider.user
                job.status = DeliveryJob.Status.ASSIGNED
                job.save()

                # Mark Busy
                rider.is_available = False
                rider.save()

                broadcast_delivery_update(str(job.id), "ASSIGNED", {"rider_id": str(rider.id)})
                return True
            except RiderProfile.DoesNotExist:
                continue # Already taken
        
        return False

    @staticmethod
    @transaction.atomic
    def update_job_status(job_id: str, status: str, user):
        job = DeliveryJob.objects.select_for_update().get(id=job_id)
        
        if job.rider != user:
            raise BusinessLogicException("Not authorized.")

        job.status = status
        
        if status == DeliveryJob.Status.PICKED_UP:
            job.pickup_time = timezone.now()
            
        elif status == DeliveryJob.Status.COMPLETED:
            job.completion_time = timezone.now()
            
            # Release Rider
            from apps.riders.services import RiderService
            RiderService.mark_available(user)
            
            Order.objects.filter(id=job.order_id).update(status='DELIVERED') # Use string or Order.Status

        job.save()
        broadcast_delivery_update(str(job.id), status, {})
        return job