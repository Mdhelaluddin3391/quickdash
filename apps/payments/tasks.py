# apps/payments/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from .models import Payment
from .services import initiate_refund
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_refund_task(payment_id):
    """
    Background task jo refund process karega.
    Agar fail hua, toh Celery automatic retry kar sakta hai (Advanced).
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Service call karein
        success, result = initiate_refund(payment)
        
        if success:
            logger.info(f"Refund Successful for Payment ID {payment_id}")
            
            # Optional: User ko email bhejein
            # send_mail(
            #     'Refund Processed',
            #     f'Your refund for order {payment.order.id} has been processed.',
            #     'support@quickdash.com',
            #     [payment.user.email],
            #     fail_silently=True,
            # )
        else:
            logger.error(f"Refund Failed for Payment ID {payment_id}: {result}")
            
    except Payment.DoesNotExist:
        logger.error(f"Payment ID {payment_id} not found for refund.")