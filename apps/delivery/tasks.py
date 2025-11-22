# apps/delivery/tasks.py
import logging
import random

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.warehouse.models import Warehouse
from apps.accounts.models import RiderProfile as RiderProfileModel
from .models import DeliveryTask
from .signals import rider_assigned_to_dispatch
from .utils import haversine_distance  # assuming already present
from django.conf import settings


logger = logging.getLogger(__name__)


def _generate_otp(length: int = 4) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def _find_best_rider_for_warehouse(
    warehouse_id: str,
) -> RiderProfileModel | None:
    """
    PRO matching algo:

    1) Active Warehouse location
    2) Riders with on_duty=True
    3) Riders not already busy on active task
    4) Minimum distance within MAX_RADIUS_KM
    """
    MAX_RADIUS_KM = getattr(settings, "RIDER_MAX_RADIUS_KM", 10.0) # <--- Clean access
    try:
        warehouse = Warehouse.objects.get(id=warehouse_id)
        if warehouse.lat is None or warehouse.lng is None:
            logger.error(
                "Warehouse %s has no coordinates (lat/lng)", warehouse.code
            )
            return None

        wh_lat = float(warehouse.lat)
        wh_lng = float(warehouse.lng)
    except Warehouse.DoesNotExist:
        logger.error("Warehouse %s does not exist", warehouse_id)
        return None

    candidates = (
        RiderProfileModel.objects.filter(on_duty=True)
        .select_related("user")
        .only("id", "rider_code", "current_location", "on_duty")
    )

    if not candidates.exists():
        logger.warning("No on-duty riders for warehouse %s", warehouse_id)
        return None

    # busy riders (any non-terminal task for them)
    busy_rider_ids = DeliveryTask.objects.filter(
        status__in=[
            DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT,
            DeliveryTask.DeliveryStatus.ACCEPTED,
            DeliveryTask.DeliveryStatus.AT_STORE,
            DeliveryTask.DeliveryStatus.PICKED_UP,
        ]
    ).values_list("rider_id", flat=True)

    MAX_RADIUS_KM = float(
        getattr(
            __import__("django.conf").conf.settings,
            "RIDER_MAX_RADIUS_KM",
            10.0,
        )
    )

    best_rider = None
    min_distance = float("inf")

    for profile in candidates:
        if profile.id in busy_rider_ids:
            continue
        if not profile.current_location:
            continue

        rider_lng = float(profile.current_location.x)
        rider_lat = float(profile.current_location.y)

        dist = haversine_distance(wh_lat, wh_lng, rider_lat, rider_lng)

        if dist < min_distance and dist <= MAX_RADIUS_KM:
            min_distance = dist
            best_rider = profile

    if best_rider:
        logger.info(
            "Selected Rider %s for warehouse %s (%.2f km)",
            best_rider.rider_code,
            warehouse_id,
            min_distance,
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
    """
    Background assignment:

    - Finds best rider near warehouse
    - Assigns to DeliveryTask
    - Emits rider_assigned_to_dispatch signal
    """
    try:
        task = DeliveryTask.objects.select_for_update().get(id=delivery_task_id)
    except DeliveryTask.DoesNotExist:
        logger.error("DeliveryTask %s does not exist", delivery_task_id)
        return

    if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
        logger.info(
            "Task %s not pending assignment (status=%s), skipping",
            delivery_task_id,
            task.status,
        )
        return

    try:
        best_rider = _find_best_rider_for_warehouse(warehouse_id)
        if not best_rider:
            logger.info(
                "No rider found for task %s, retrying later", task.id
            )
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
        logger.exception(
            "Error while assigning rider for task %s: %s",
            delivery_task_id,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task
def create_delivery_task_from_signal(
    dispatch_id: str, order_id: str, warehouse_id: str, pickup_otp: str
):
    """
    WMS dispatch_ready_for_delivery signal se call hota hai. :contentReference[oaicite:2]{index=2}

    - Order se DeliveryTask create karega (if not exists)
    - Rider assignment background me trigger karega
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("Order %s not found for delivery creation", order_id)
        return

    warehouse_id = str(warehouse_id)

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
                logger.info(
                    "DeliveryTask %s created for Order %s (dispatch %s)",
                    task.id,
                    order.id,
                    dispatch_id,
                )
                find_and_assign_rider_for_task.delay(
                    delivery_task_id=str(task.id),
                    warehouse_id=warehouse_id,
                )
            else:
                logger.info(
                    "DeliveryTask already exists for dispatch %s (task %s)",
                    dispatch_id,
                    task.id,
                )
    except Exception:
        logger.exception(
            "Error creating delivery task for dispatch %s / order %s",
            dispatch_id,
            order_id,
        )
