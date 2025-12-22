import logging
from celery import shared_task
from django.conf import settings
from .services import DeliveryService
from .models import DeliveryTask
from apps.riders.services import RiderAssignmentService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=10, default_retry_delay=30)
def assign_rider_to_task_job(self, task_id: str):
    """
    Finds the nearest available rider and assigns them to the task.
    """
    try:
        task = DeliveryTask.objects.get(id=task_id)
        
        if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
            logger.info(f"Task {task_id} already assigned or cancelled.")
            return

        # 1. Get Delivery Location (Warehouse Location for pickup)
        # Assuming order.warehouse has lat/lng
        wh = task.order.warehouse
        
        # 2. Find Riders via Spatial Service
        riders = RiderAssignmentService.find_eligible_riders_nearby(
            lat=wh.latitude, 
            lng=wh.longitude, 
            radius_km=settings.RIDER_MAX_RADIUS_KM
        )

        if not riders.exists():
            logger.warning(f"No riders found for task {task_id}. Retrying...")
            raise self.retry()

        # 3. Assign First Available
        # In a real system, you might broadcast to all and wait for acceptance.
        # Here we assign to the closest one (Greedy approach).
        best_rider = riders.first()
        
        DeliveryService.assign_rider(task.id, best_rider.id)
        logger.info(f"Assigned Rider {best_rider.id} to Task {task.id}")

    except DeliveryTask.DoesNotExist:
        logger.error(f"DeliveryTask {task_id} not found.")
    except Exception as e:
        logger.exception(f"Error assigning rider: {e}")
        raise self.retry(exc=e)