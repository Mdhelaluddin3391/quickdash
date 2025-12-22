import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError

# Domain Imports
from apps.orders.models import Order
from apps.accounts.models import RiderProfile, RiderStatus
from apps.riders.services import RiderAssignmentService
from .models import DeliveryTask, RiderEarning
from .signals import delivery_task_created, delivery_completed, rider_assigned_to_dispatch
from .utils import broadcast_delivery_update

logger = logging.getLogger(__name__)

class DeliveryService:
    
    @staticmethod
    @transaction.atomic
    def create_task_from_dispatch(order_id: str, dispatch_id: str, warehouse_otp: str):
        """
        Called by WMS when order is packed and ready.
        """
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise ValidationError(f"Order {order_id} not found.")

        if hasattr(order, 'delivery_task'):
            return order.delivery_task # Idempotency

        # Generate Secure OTP for Customer Delivery
        import secrets
        delivery_otp = str(secrets.randbelow(999999)).zfill(6)

        task = DeliveryTask.objects.create(
            order=order,
            dispatch_record_id=dispatch_id,
            status=DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT,
            pickup_otp=warehouse_otp,
            delivery_otp=delivery_otp
        )
        
        logger.info(f"Delivery Task Created: {task.id}")
        
        # Trigger Async Rider Assignment
        from .tasks import assign_rider_to_task_job
        assign_rider_to_task_job.delay(str(task.id))
        
        return task

    @staticmethod
    @transaction.atomic
    def assign_rider(task_id: str, rider_id: str):
        """
        Assigns a specific rider to a task.
        """
        task = DeliveryTask.objects.select_for_update().get(id=task_id)
        rider = RiderProfile.objects.select_for_update().get(id=rider_id)

        if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
            raise ValidationError("Task is no longer pending assignment.")

        if rider.current_status != RiderStatus.ONLINE:
            raise ValidationError("Rider is not available.")

        # 1. Update Task
        task.rider = rider
        task.status = DeliveryTask.DeliveryStatus.ASSIGNED
        task.assigned_at = timezone.now()
        task.save()

        # 2. Lock Rider
        rider.current_status = RiderStatus.BUSY
        rider.save(update_fields=['current_status'])

        # 3. Notify Systems
        rider_assigned_to_dispatch.send(sender=DeliveryService, dispatch_id=task.dispatch_record_id, rider_profile_id=rider.id)
        broadcast_delivery_update(task, event_type="rider_assigned")
        
        return task

    @staticmethod
    @transaction.atomic
    def rider_accept_task(task_id: str, rider_user):
        """
        Rider Acknowledges/Accepts the job.
        """
        task = DeliveryTask.objects.select_for_update().get(id=task_id)
        
        if task.rider.user != rider_user:
            raise ValidationError("Unauthorized access to task.")
            
        if task.status != DeliveryTask.DeliveryStatus.ASSIGNED:
            raise ValidationError("Task cannot be accepted in current state.")

        task.status = DeliveryTask.DeliveryStatus.ACCEPTED
        task.accepted_at = timezone.now()
        task.save()
        
        broadcast_delivery_update(task, event_type="order_accepted")
        return task

    @staticmethod
    @transaction.atomic
    def process_pickup(task_id: str, rider_user, otp: str):
        """
        Rider picks up package from Warehouse (Verifies Warehouse OTP).
        """
        task = DeliveryTask.objects.select_for_update().get(id=task_id)
        
        if task.rider.user != rider_user:
            raise ValidationError("Unauthorized.")

        if task.pickup_otp != otp:
            raise ValidationError("Invalid Pickup OTP.")

        task.status = DeliveryTask.DeliveryStatus.PICKED_UP
        task.picked_up_at = timezone.now()
        task.save()

        # Explicitly Update Order Status
        from apps.orders.services import OrderService
        OrderService.dispatch_order(str(task.order.id))

        broadcast_delivery_update(task, event_type="order_picked_up")
        return task

    @staticmethod
    @transaction.atomic
    def complete_delivery(task_id: str, rider_user, otp: str):
        """
        Rider delivers to Customer (Verifies Delivery OTP).
        """
        task = DeliveryTask.objects.select_for_update().get(id=task_id)
        
        if task.rider.user != rider_user:
            raise ValidationError("Unauthorized.")

        if task.delivery_otp != otp:
            raise ValidationError("Invalid Delivery OTP.")

        task.status = DeliveryTask.DeliveryStatus.DELIVERED
        task.delivered_at = timezone.now()
        task.save()

        # 1. Release Rider
        rider = task.rider
        rider.current_status = RiderStatus.ONLINE
        rider.save(update_fields=['current_status'])

        # 2. Calculate & Create Earning
        base_fee = getattr(settings, 'RIDER_BASE_FEE', Decimal('30.00'))
        RiderEarning.objects.create(
            rider=rider,
            delivery_task=task,
            amount=base_fee,
            is_settled=False
        )

        # 3. Update Order Status (Explicit Call)
        # Note: OrderService needs a method for 'delivered' or generic update
        task.order.status = 'DELIVERED' 
        task.order.delivered_at = timezone.now()
        task.order.save(update_fields=['status', 'delivered_at'])

        # 4. Signals & Broadcasts
        delivery_completed.send(sender=DeliveryTask, order=task.order, rider_code=rider.rider_code)
        broadcast_delivery_update(task, event_type="order_delivered")
        
        return task