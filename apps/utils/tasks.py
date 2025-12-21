from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_logs_task():
    logger.info("Running log cleanup... (extend logic here)")
    return True
