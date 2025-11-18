# apps/delivery/tasks.py
import logging
import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone

# Zaroori models ko import karein
from apps.accounts.models import RiderProfile, User
from apps.orders.models import Order
from .models import DeliveryTask, RiderLocation
from .signals import rider_assigned_to_dispatch


logger = logging.getLogger(__name__)

def _generate_otp(length=4):
    """Helper function to generate a simple numeric OTP."""
    return "".join(str(random.randint(0, 9)) for _ in range(length))

def _find_best_rider_for_warehouse(warehouse_id: str) -> RiderProfile | None:
    """
    Sabse achha (available) rider dhoondhta hai.
    """
    
    # 1. Sabhi on-duty riders ko dhoondein
    on_duty_locations = RiderLocation.objects.filter(on_duty=True).select_related('rider').order_by('-timestamp')
    
    if not on_duty_locations.exists():
        logger.warning(f"No riders are on duty for warehouse {warehouse_id}.")
        return None

    # 2. Un riders ki IDs lein jinke paas pehle se active task hai
    active_rider_ids = DeliveryTask.objects.filter(
        status__in=["assigned", "at_warehouse", "picked_up", "at_customer"]
    ).values_list('rider_id', flat=True)

    # 3. Pehla aisa rider dhoondein jo on_duty hai, lekin active task list mein nahi hai
    for loc in on_duty_locations:
        if str(loc.rider_id) not in [str(id) for id in active_rider_ids]: # Compare UUIDs as strings
            logger.info(f"Found available rider: {loc.rider.rider_code}")
            return loc.rider 

    logger.warning(f"All on-duty riders are busy for warehouse {warehouse_id}.")
    return None 


@shared_task(bind=True, max_retries=12, default_retry_delay=300) 
def find_and_assign_rider_for_task(self, delivery_task_id: str, warehouse_id: str):
    """
    Ek specific delivery task ke liye rider dhoondhta hai aur assign karta hai.
    """
    try:
        task = DeliveryTask.objects.select_related('order').get(id=delivery_task_id)
    except DeliveryTask.DoesNotExist:
        logger.warning(f"DeliveryTask {delivery_task_id} not found for assignment.")
        return f"Task {delivery_task_id} not found."
        
    if task.status != "pending_assignment":
        logger.info(f"Task {task.id} is already {task.status}. Skipping assignment.")
        return f"Task {task.id} already processed."

    try:
        best_rider = _find_best_rider_for_warehouse(warehouse_id)
        
        if not best_rider:
            logger.info(f"No available riders found for task {task.id}. Retrying in 5 mins...")
            raise self.retry()

        with transaction.atomic():
            # Rider ki User ID (Order model mein save karne ke liye)
            rider_user = User.objects.get(id=best_rider.user_id)

            # Task ko update karo
            task.rider = best_rider
            task.status = "assigned"
            task.assigned_at = timezone.now()
            task.delivery_otp = _generate_otp(4) # Customer ke liye naya OTP
            task.save()
            
            # WMS (DispatchRecord) aur Orders app ko update karne ke liye signal bhejein
            rider_assigned_to_dispatch.send(
                sender=DeliveryTask,
                dispatch_id=task.dispatch_record_id,
                rider_profile_id=best_rider.id,
                order_id=task.order_id, 
                rider_user_id=rider_user.id 
            )

        logger.info(f"Task {task.id} assigned to Rider {best_rider.rider_code}")
        
        return f"Task {task.id} assigned to {best_rider.rider_code}"

    except Exception as exc:
        logger.error(f"Failed to assign rider for task {task.id}: {exc}")
        # Next retry 60 seconds (1 minute) mein
        raise self.retry(exc=exc, countdown=60)


@shared_task
def create_delivery_task_from_signal(dispatch_id, order_id, warehouse_id, pickup_otp):
    """
    Yeh task WMS ke signal se trigger hota hai.
    Yeh DeliveryTask banata hai aur rider assignment ko trigger karta hai.
    """
    logger.info(f"Creating DeliveryTask for Dispatch {dispatch_id}...")
    
    try:
        order = Order.objects.get(id=order_id)
        
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
                # Naya task ban gaya, ab iske liye rider dhoondhne ka task trigger karein
                find_and_assign_rider_for_task.delay(
                    delivery_task_id=str(task.id),
                    warehouse_id=str(warehouse_id)
                )
                logger.info(f"DeliveryTask {task.id} created for Dispatch {dispatch_id}.")
            else:
                logger.warning(f"DeliveryTask for Dispatch {dispatch_id} already exists.")
                
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found. Cannot create DeliveryTask for Dispatch {dispatch_id}.")
    except Exception as e:
        logger.error(f"Failed to create DeliveryTask for Dispatch {dispatch_id}: {e}")