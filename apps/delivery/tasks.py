# apps/delivery/tasks.py
import logging
import random

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from apps.orders.models import Order
from apps.warehouse.models import Warehouse
from apps.accounts.models import RiderProfile as RiderProfileModel
from .models import DeliveryTask
from .signals import rider_assigned_to_dispatch

logger = logging.getLogger(__name__)


def _generate_otp(length: int = 4) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def _find_best_rider_for_warehouse(warehouse_id: str) -> RiderProfileModel | None:
    """
    PRO matching algo (Fixed for Performance):
    1) Uses PostGIS DB query to find nearest rider (No Python loops).
    2) Filters within MAX_RADIUS_KM.
    3) Excludes busy riders.
    """
    MAX_RADIUS_KM = getattr(settings, "RIDER_MAX_RADIUS_KM", 10.0)

    try:
        warehouse = Warehouse.objects.get(id=warehouse_id)
        if warehouse.lat is None or warehouse.lng is None:
            logger.error("Warehouse %s has no coordinates", warehouse.code)
            return None
        
        # Create Point object for warehouse (Longitude, Latitude)
        warehouse_location = Point(float(warehouse.lng), float(warehouse.lat), srid=4326)

    except Warehouse.DoesNotExist:
        logger.error("Warehouse %s does not exist", warehouse_id)
        return None

    # Find riders who are busy
    busy_rider_ids = DeliveryTask.objects.filter(
        status__in=[
            DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT,
            DeliveryTask.DeliveryStatus.ACCEPTED,
            DeliveryTask.DeliveryStatus.AT_STORE,
            DeliveryTask.DeliveryStatus.PICKED_UP,
        ]
    ).values_list("rider_id", flat=True)

    # DB Optimization: Filter by distance & duty directly in SQL
    best_rider = RiderProfileModel.objects.filter(
        on_duty=True,
        current_location__distance_lte=(warehouse_location, D(km=MAX_RADIUS_KM))
    ).exclude(
        id__in=busy_rider_ids
    ).annotate(
        distance=Distance('current_location', warehouse_location)
    ).order_by('distance').first()

    if best_rider:
        logger.info(
            "Selected Rider %s for warehouse %s (Distance: %.2f m)",
            best_rider.rider_code,
            warehouse_id,
            best_rider.distance.m,
        )
    else:
        logger.warning(
            "No available riders within %.2f km for warehouse %s",
            MAX_RADIUS_KM,
            warehouse_id,
        )

    return best_rider


@shared_task(bind=True, max_retries=5, default_retry_delay=15)
def find_and_assign_rider_for_task(self, delivery_task_id: str, warehouse_id: str):
    try:
        task = DeliveryTask.objects.select_for_update().get(id=delivery_task_id)
    except DeliveryTask.DoesNotExist:
        logger.error("DeliveryTask %s does not exist", delivery_task_id)
        return

    if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
        logger.info("Task %s not pending assignment, skipping", delivery_task_id)
        return

    try:
        best_rider = _find_best_rider_for_warehouse(warehouse_id)
        
        if not best_rider:
            logger.info("No rider found for task %s, retrying later", task.id)
            # Retry this task after delay
            raise self.retry()

        with transaction.atomic():
            rider_user = best_rider.user

            task.rider = best_rider
            task.status = DeliveryTask.DeliveryStatus.ACCEPTED
            task.accepted_at = timezone.now()
            task.delivery_otp = _generate_otp(4)
            task.save()

            rider_assigned_to_dispatch.send(
                sender=DeliveryTask,
                dispatch_id=task.dispatch_record_id,
                rider_profile_id=best_rider.id,
                order_id=task.order_id,
                rider_user_id=rider_user.id,
            )

        return f"Task {task.id} assigned to rider {best_rider.rider_code}"

    except Exception as exc:
        logger.exception("Error assigning rider for task %s: %s", delivery_task_id, exc)
        raise self.retry(exc=exc)


@shared_task
def create_delivery_task_from_signal(dispatch_id: str, order_id: str, warehouse_id: str, pickup_otp: str):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("Order %s not found for delivery creation", order_id)
        return

    try:
        with transaction.atomic():
            task, created = DeliveryTask.objects.get_or_create(
                dispatch_record_id=str(dispatch_id),
                defaults={
                    "order": order,
                    "status": DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT,
                    "pickup_otp": pickup_otp,
                },
            )

            if created:
                logger.info("DeliveryTask %s created for Order %s", task.id, order.id)
                find_and_assign_rider_for_task.delay(
                    delivery_task_id=str(task.id),
                    warehouse_id=str(warehouse_id),
                )
    except Exception:
        logger.exception("Error creating delivery task for dispatch %s", dispatch_id)