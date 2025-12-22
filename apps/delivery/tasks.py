from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def assign_rider_task(self, job_id):
    from .services import DeliveryService
    
    try:
        success = DeliveryService.assign_nearest_rider(job_id)
        if not success:
            # No rider found? Retry.
            logger.info(f"No rider found for Job {job_id}. Retrying...")
            raise self.retry()
    except Exception as e:
        logger.error(f"Error assigning rider: {e}")
        raise self.retry(exc=e)

def broadcast_delivery_update(job_id, status, data):
    """
    Sends WS message to group 'delivery_{job_id}'
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"delivery_{job_id}",
        {
            "type": "delivery_update",
            "status": status,
            "data": data
        }
    )