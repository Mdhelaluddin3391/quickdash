# apps/inventory/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from .models import InventoryStock
# Warehouse/SKU models ko yahan import kiya gaya hai (Agar zaroori ho, ya IDs se kaam chalaya jaye)
from apps.warehouse.models import Warehouse 
from apps.catalog.models import SKU 

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
@transaction.atomic
def update_inventory_stock_task(self, sku_id, warehouse_id, delta_available, delta_reserved):
    """
    Warehouse signals se received inventory update ko process karta hai.
    """
    try:
        # Stock ko lock karein aur update/create karein
        stock, created = InventoryStock.objects.select_for_update().get_or_create(
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            defaults={'available_qty': 0, 'reserved_qty': 0}
        )

        stock.available_qty += delta_available
        stock.reserved_qty += delta_reserved

        if stock.available_qty < 0:
             logger.error(f"Integrity Error: Available Qty went negative for SKU {sku_id} in WH {warehouse_id}.")
             raise ValueError("Available quantity cannot be negative.")
        
        if stock.reserved_qty < 0:
             logger.error(f"Integrity Error: Reserved Qty went negative for SKU {sku_id} in WH {warehouse_id}.")
             raise ValueError("Reserved quantity cannot be negative.")

        stock.save()
        logger.info(f"InventoryStock updated for {sku_id}@{warehouse_id}: Avail Delta {delta_available}, Res Delta {delta_reserved}")

    except Exception as exc:
        logger.error(f"Failed to update InventoryStock {sku_id}@{warehouse_id}: {exc}")
        raise self.retry(exc=exc)