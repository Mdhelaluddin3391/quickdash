# apps/inventory/receivers.py
import logging
from django.dispatch import receiver
from apps.warehouse.signals import inventory_change_required # Warehouse signal import
from .tasks import update_inventory_stock_task

logger = logging.getLogger(__name__)

@receiver(inventory_change_required)
def handle_inventory_change_signal(sender, sku_id, warehouse_id, delta_available, delta_reserved, reference, change_type, **kwargs):
    """
    Warehouse app से inventory_change_required signal प्राप्त करता है और 
    अपडेट को Celery task में भेजता है।
    """
    logger.info(
        f"Received inventory change signal: Ref={reference}, Type={change_type}, "
        f"Sku={sku_id}, Avl={delta_available}, Res={delta_reserved}"
    )
    
    # Celery task को ट्रिगर करें (actual DB change task में होगा)
    update_inventory_stock_task.delay(
        sku_id=str(sku_id), 
        warehouse_id=str(warehouse_id), 
        delta_available=delta_available, 
        delta_reserved=delta_reserved
    )