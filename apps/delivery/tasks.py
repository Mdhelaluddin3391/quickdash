from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from apps.orders.models import Order
from apps.delivery.services import RiderService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def find_and_assign_rider_for_task(self, order_id):
    try:
        order = Order.objects.get(id=order_id)
        
        # Try to find rider
        rider = RiderService.find_nearby_rider(order.location)
        
        if rider:
            RiderService.assign_order(rider, order)
            return f"Assigned to {rider.name}"
        else:
            # If no rider, retry
            raise self.retry(exc=Exception("No rider available"))

    except MaxRetriesExceededError:
        # CRITICAL FALLBACK: Don't let the order die
        logger.critical(f"Order {order_id} failed auto-assignment after 5 attempts.")
        
        order.status = 'MANUAL_ASSIGNMENT_REQUIRED'
        order.internal_notes = "Auto-assignment failed. Requires Dispatcher attention."
        order.save()
        
        # Optional: Send Slack/Email alert to Ops Team
        # OpsAlert.send(f"Order {order_id} needs manual dispatch!")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found.")