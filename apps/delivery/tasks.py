# apps/delivery/tasks.py

from celery import shared_task
from django.db import transaction

from .services import DeliveryService
from .models import DeliveryTask
from apps.riders.models import Rider


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def assign_rider_job(self, task_id: str):
    """
    ONLY async entry point for rider assignment.
    """
    try:
        task = DeliveryTask.objects.select_related("order").get(id=task_id)

        # Rider selection logic (simplified)
        rider = Rider.objects.filter(is_available=True).first()
        if not rider:
            raise Exception("No rider available")

        with transaction.atomic():
            DeliveryService.assign_rider(task_id, rider)

    except Exception as exc:
        raise self.retry(exc=exc)
