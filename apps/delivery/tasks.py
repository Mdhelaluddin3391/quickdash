import logging
import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone

# Zaroori models ko import karein
from apps.warehouse.models import DispatchRecord, Warehouse
from apps.accounts.models import RiderProfile
from .models import DeliveryTask, RiderLocation

logger = logging.getLogger(__name__)

def _generate_otp(length=4):
    """Helper function to generate a simple numeric OTP."""
    return "".join(str(random.randint(0, 9)) for _ in range(length))

def _find_best_rider_for_warehouse(warehouse: Warehouse) -> RiderProfile | None:
    """
    Sabse achha (available) rider dhoondhta hai.
    System Design[cite: 165, 168]: "Optimized rider assignment based on distance... and online state"
    """
    
    # TODO: Asli system mein, yahaan warehouse ke (lat, lng) ke
    # aaspas waale nazdeeki riders ko dhoondhna chahiye. (Geospatial query)
    
    # 1. Sabhi on-duty riders ko dhoondein
    on_duty_locations = RiderLocation.objects.filter(on_duty=True).select_related('rider')
    
    if not on_duty_locations.exists():
        logger.warning(f"No riders are on duty for warehouse {warehouse.code}.")
        return None

    # 2. Un riders ki IDs lein jinke paas pehle se active task hai
    active_rider_ids = DeliveryTask.objects.filter(
        status__in=["assigned", "at_warehouse", "picked_up", "at_customer"]
    ).values_list('rider_id', flat=True)

    # 3. Pehla aisa rider dhoondein jo on_duty hai, lekin active task list mein nahi hai
    for loc in on_duty_locations:
        if loc.rider_id not in active_rider_ids:
            logger.info(f"Found available rider: {loc.rider.rider_code}")
            return loc.rider # Pehla free rider mil gaya

    logger.warning(f"All on-duty riders are busy for warehouse {warehouse.code}.")
    return None # Sabhi on-duty riders busy hain


@shared_task(bind=True, max_retries=12, default_retry_delay=300) # 1 ghante tak (12 * 5 min) retry karega
def find_and_assign_rider_for_task(self, delivery_task_id: str):
    """
    Ek specific delivery task ke liye rider dhoondhta hai aur assign karta hai.
    """
    try:
        task = DeliveryTask.objects.select_related(
            'dispatch_record__warehouse', 
            'order'
        ).get(id=delivery_task_id)
    except DeliveryTask.DoesNotExist:
        logger.warning(f"DeliveryTask {delivery_task_id} not found for assignment.")
        return f"Task {delivery_task_id} not found."
        
    if task.status != "pending_assignment":
        logger.info(f"Task {task.id} is already {task.status}. Skipping assignment.")
        return f"Task {task.id} already processed."

    warehouse = task.dispatch_record.warehouse
    
    try:
        best_rider = _find_best_rider_for_warehouse(warehouse)
        
        if not best_rider:
            logger.info(f"No available riders found for task {task.id}. Retrying in 5 mins...")
            # Retry karein
            raise self.retry()

        with transaction.atomic():
            # Task ko update karo
            task.rider = best_rider
            task.status = "assigned"
            task.assigned_at = timezone.now()
            task.pickup_otp = task.dispatch_record.pickup_otp # WMS se OTP copy karo
            task.delivery_otp = _generate_otp(4) # Customer ke liye naya OTP
            task.save()
            
            # DispatchRecord ko bhi update karo
            dispatch = task.dispatch_record
            dispatch.status = "assigned"
            dispatch.rider_id = str(best_rider.id) # RiderProfile ka ID
            dispatch.save(update_fields=['status', 'rider_id'])
            
            # Order ko bhi update karo (taki customer ko dikhe)
            if task.order:
                task.order.status = "dispatched"
                task.order.rider = best_rider.user # User model ko link karo
                task.order.save(update_fields=['status', 'rider'])

        logger.info(f"Task {task.id} assigned to Rider {best_rider.rider_code}")
        
        # TODO: Yahaan Rider ko Push Notification (FCM) bhejna chahiye
        # notify_rider_new_task(best_rider, task)
        
        return f"Task {task.id} assigned to {best_rider.rider_code}"

    except Exception as exc:
        logger.error(f"Failed to assign rider for task {task.id}: {exc}")
        raise self.retry(exc=exc, countdown=60) # Koi aur error aaye toh 1 min mein retry


@shared_task
def create_delivery_tasks_from_dispatch():
    """
    Yeh task Celery Beat se har minute chalna chahiye.
    Yeh "ready" DispatchRecords ko dhoondhta hai aur unke liye DeliveryTasks banata hai.
    """
    logger.info("Running create_delivery_tasks_from_dispatch...")
    
    # Un DispatchRecords ko dhoondein jo 'ready' hain aur jinka 'delivery_task' abhi nahi bana hai
    ready_dispatches = DispatchRecord.objects.filter(
        status="ready",
        delivery_task__isnull=True
    ).select_related('packing_task__picking_task__order') # Order fetch karne ke liye

    if not ready_dispatches.exists():
        logger.info("No new 'ready' dispatches found.")
        return "No new dispatches."

    tasks_created_count = 0
    for dispatch in ready_dispatches:
        try:
            # Har dispatch ke liye ek naya DeliveryTask banayein
            # transaction.atomic() ka istemaal, taaki duplicate na bane
            with transaction.atomic():
                task, created = DeliveryTask.objects.get_or_create(
                    dispatch_record=dispatch,
                    defaults={
                        'order': dispatch.packing_task.picking_task.order,
                        'status': "pending_assignment",
                        'pickup_otp': dispatch.pickup_otp
                    }
                )
                
                if created:
                    # Naya task ban gaya, ab iske liye rider dhoondhne ka task trigger karein
                    find_and_assign_rider_for_task.delay(str(task.id))
                    tasks_created_count += 1
                
        except Exception as e:
            # Agar DeliveryTask banate waqt error aaye
            logger.error(f"Failed to create DeliveryTask for Dispatch {dispatch.id}: {e}")
    
    logger.info(f"Created {tasks_created_count} new delivery tasks.")
    return f"Created {tasks_created_count} new tasks."