# apps/delivery/tasks.py
import logging
import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

# Imports
from apps.accounts.models import RiderProfile, User
from apps.orders.models import Order
from apps.warehouse.models import Warehouse # Warehouse model import kiya
from .models import DeliveryTask, RiderLocation
from .signals import rider_assigned_to_dispatch
from .utils import haversine_distance # Math function import kiya

logger = logging.getLogger(__name__)

def _generate_otp(length=4):
    return "".join(str(random.randint(0, 9)) for _ in range(length))

def _find_best_rider_for_warehouse(warehouse_id: str) -> RiderProfile | None:
    """
    PRO ALGORITHM:
    1. Warehouse ki location nikalo.
    2. Sirf 'Available' (On-Duty + No Active Task) riders ko filter karo.
    3. Har rider ka Warehouse se distance calculate karo.
    4. Sabse kam distance wale rider ko return karo.
    """
    try:
        warehouse = Warehouse.objects.get(id=warehouse_id)
        if not warehouse.lat or not warehouse.lng:
            logger.error(f"Warehouse {warehouse.code} has no coordinates!")
            return None
            
        wh_lat = float(warehouse.lat)
        wh_lng = float(warehouse.lng)
        
    except Warehouse.DoesNotExist:
        return None

    # 1. Wo Riders jo On-Duty hain
    # Note: select_related se DB queries kam hongi
    candidate_locations = RiderLocation.objects.filter(
        on_duty=True
    ).select_related('rider')

    if not candidate_locations.exists():
        logger.warning(f"No riders are on duty for WH {warehouse_id}.")
        return None

    # 2. Wo Riders jo Busy hain (Jinka task active hai)
    busy_rider_ids = DeliveryTask.objects.filter(
        status__in=["assigned", "at_warehouse", "picked_up", "at_customer"]
    ).values_list('rider_id', flat=True)

    # 3. Best Rider Select Karo (Loop through candidates)
    best_rider = None
    min_distance = float('inf')
    
    # Configurable: Rider maximum kitni door ho sakta hai? (e.g., 10 km)
    MAX_RADIUS_KM = 10.0 

    for loc in candidate_locations:
        # Agar rider busy hai to skip karo
        if loc.rider_id in busy_rider_ids:
            continue
            
        # Distance Calculate karo
        # Decimal ko float mein convert karna zaroori hai math operations ke liye
        rider_lat = float(loc.lat)
        rider_lng = float(loc.lng)
        
        dist = haversine_distance(wh_lat, wh_lng, rider_lat, rider_lng)
        
        # Debug log (Development mein helpful)
        # logger.debug(f"Rider {loc.rider.rider_code} distance: {dist:.2f} km")

        if dist < min_distance and dist <= MAX_RADIUS_KM:
            min_distance = dist
            best_rider = loc.rider

    if best_rider:
        logger.info(f"Selected Rider {best_rider.rider_code} (Dist: {min_distance:.2f} km)")
    else:
        logger.warning("No available riders found within range.")

    return best_rider 


@shared_task(bind=True, max_retries=12, default_retry_delay=60) # Retry har 1 min (total 12 mins)
def find_and_assign_rider_for_task(self, delivery_task_id: str, warehouse_id: str):
    """
    Rider assignment task (Updated logic ke sath).
    """
    try:
        task = DeliveryTask.objects.select_related('order').get(id=delivery_task_id)
    except DeliveryTask.DoesNotExist:
        return f"Task {delivery_task_id} not found."
        
    if task.status != "pending_assignment":
        return f"Task {task.id} already processed."

    try:
        # Algorithm call karein
        best_rider = _find_best_rider_for_warehouse(warehouse_id)
        
        if not best_rider:
            logger.info(f"No rider found for task {task.id}. Retrying...")
            # Retry karein
            raise self.retry()

        with transaction.atomic():
            rider_user = User.objects.get(id=best_rider.user_id)

            task.rider = best_rider
            task.status = "assigned"
            task.assigned_at = timezone.now()
            task.delivery_otp = _generate_otp(4)
            task.save()
            
            rider_assigned_to_dispatch.send(
                sender=DeliveryTask,
                dispatch_id=task.dispatch_record_id,
                rider_profile_id=best_rider.id,
                order_id=task.order_id, 
                rider_user_id=rider_user.id 
            )

        return f"Task {task.id} assigned to {best_rider.rider_code}"

    except Exception as exc:
        logger.error(f"Assignment Logic Error: {exc}")
        raise self.retry(exc=exc)

# ... create_delivery_task_from_signal same rahega ...
@shared_task
def create_delivery_task_from_signal(dispatch_id, order_id, warehouse_id, pickup_otp):
    try:
        order = Order.objects.get(id=order_id)
        # Warehouse ID ensure string ho
        warehouse_id = str(warehouse_id) 
        
        with transaction.atomic():
            task, created = DeliveryTask.objects.get_or_create(
                dispatch_record_id=dispatch_id, 
                defaults={
                    'order': order,
                    'status': "pending_assignment",
                    'pickup_otp': pickup_otp
                }
            )
            if created:
                find_and_assign_rider_for_task.delay(
                    delivery_task_id=str(task.id),
                    warehouse_id=warehouse_id
                )
    except Exception as e:
        logger.error(f"Error creating delivery task: {e}")