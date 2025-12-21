from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction, DatabaseError
from .models import InventoryStock, InventoryHistory
from django.core.management import call_command

@shared_task
def run_reconciliation():
    call_command("reconcile_inventory")

    
logger = get_task_logger(__name__)

@shared_task(
    bind=True, 
    max_retries=5, 
    default_retry_delay=10,
    autoretry_for=(DatabaseError,),
    retry_backoff=True
)
def update_inventory_stock_task(self, sku_id, warehouse_id, delta_available, delta_reserved, reference, change_type):
    """
    Updates central inventory with strict locking and idempotency checks.
    """
    try:
        with transaction.atomic():
            # Select for update to prevent race conditions during write
            stock, created = InventoryStock.objects.select_for_update().get_or_create(
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                defaults={'available_qty': 0, 'reserved_qty': 0}
            )

            # Idempotency check: Check if this reference was already processed
            # Note: This requires the History table to be reliable.
            if InventoryHistory.objects.filter(
                stock=stock, 
                reference=reference, 
                change_type=change_type
            ).exists():
                logger.info(f"Duplicate inventory event skipped: {reference}")
                return "Duplicate Skipped"

            # Apply Deltas
            stock.available_qty += delta_available
            stock.reserved_qty += delta_reserved
            stock.save()

            # Create Audit Trail
            InventoryHistory.objects.create(
                stock=stock,
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                delta_available=delta_available,
                delta_reserved=delta_reserved,
                available_after=stock.available_qty,
                reserved_after=stock.reserved_qty,
                reference=reference,
                change_type=change_type
            )

        logger.info(f"Stock Updated: SKU {sku_id} Avail={stock.available_qty}")
        return f"Updated {stock.id}"

    except Exception as exc:
        logger.error(f"Inventory Update Failed: {exc}")
        raise exc


# apps/inventory/tasks.py

@shared_task
def nightly_inventory_reconciliation():
    """
    Re-aggregates physical stock into logical stock.
    FIX: Respects reserved_qty to prevent overwriting active allocations.
    """
    from apps.warehouse.models import BinInventory
    from apps.inventory.models import InventoryStock
    from django.db.models import Sum, F
    from django.db import transaction

    # 1. Calculate Physical Totals per SKU/Warehouse
    physical_totals = BinInventory.objects.values('sku_id', 'bin__zone__warehouse_id').annotate(
        total_physical=Sum('qty')
    )

    for entry in physical_totals:
        sku_id = entry['sku_id']
        warehouse_id = entry['bin__zone__warehouse_id']
        total_physical = entry['total_physical']

        with transaction.atomic():
            # Lock the stock record
            stock, _ = InventoryStock.objects.select_for_update().get_or_create(
                sku_id=sku_id, 
                warehouse_id=warehouse_id,
                defaults={'available_qty': 0, 'reserved_qty': 0}
            )
            
            # FIX: Available = Physical - Reserved
            # We assume reserved_qty is correct (source of truth for allocations)
            # We assume physical (BinInventory) is correct (source of truth for existence)
            
            new_available = total_physical - stock.reserved_qty
            
            # Safety clamp
            if new_available < 0:
                logger.critical(
                    f"Inventory Corruption Detected: SKU {sku_id} WH {warehouse_id} "
                    f"Physical {total_physical} < Reserved {stock.reserved_qty}"
                )
                new_available = 0

            stock.available_qty = new_available
            stock.save(update_fields=['available_qty'])