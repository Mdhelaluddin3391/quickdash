from celery import shared_task
from .models import Payment
from .services import initiate_refund
import logging

logger = logging.getLogger(__name__)

# --- RENAMED TASK TO MATCH IMPORT ---
@shared_task
def process_order_refund_task(payment_id):
    """
    Background task to process refunds via Razorpay.
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        success, result = initiate_refund(payment)
        
        if success:
            logger.info(f"Refund successful for payment {payment_id}")
        else:
            logger.error(f"Refund failed for payment {payment_id}: {result}")
            
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found for refund.")
    except Exception as e:
        logger.exception(f"Error in refund task: {e}")