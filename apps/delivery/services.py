# apps/delivery/services.py

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.orders.models import Order, OrderStatus
from .models import DeliveryTask


class DeliveryService:
    """
    SINGLE SOURCE OF TRUTH for delivery lifecycle.
    """

    @staticmethod
    @transaction.atomic
    def create_task_for_order(order: Order) -> DeliveryTask:
        if order.status != OrderStatus.READY_FOR_DELIVERY:
            raise ValidationError("Order not ready for delivery")

        task, created = DeliveryTask.objects.get_or_create(
            order=order,
            defaults={"status": DeliveryTask.Status.PENDING},
        )
        return task

    @staticmethod
    @transaction.atomic
    def assign_rider(task_id: str, rider):
        task = DeliveryTask.objects.select_for_update().get(id=task_id)

        if task.status != DeliveryTask.Status.PENDING:
            raise ValidationError("Task not assignable")

        task.rider = rider
        task.status = DeliveryTask.Status.ASSIGNED
        task.assigned_at = timezone.now()
        task.save(update_fields=["rider", "status", "assigned_at"])

        return task

    @staticmethod
    @transaction.atomic
    def mark_delivered(task_id: str):
        task = DeliveryTask.objects.select_for_update().get(id=task_id)

        if task.status != DeliveryTask.Status.PICKED_UP:
            raise ValidationError("Invalid state for delivery")

        task.status = DeliveryTask.Status.DELIVERED
        task.delivered_at = timezone.now()
        task.save(update_fields=["status", "delivered_at"])

        # Enum-safe order update
        order = task.order
        order.status = OrderStatus.DELIVERED
        order.save(update_fields=["status"])

        return task
