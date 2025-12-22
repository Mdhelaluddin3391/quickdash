import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Sum, F
from django.core.paginator import Paginator
from apps.warehouse.models import BinInventory, Warehouse
from .models import InventoryStock, StockMovementLog

logger = logging.getLogger("django")

@shared_task
def trigger_reconciliations():
    """
    MASTER TASK:
    Instead of doing work, it just spawns smaller tasks per warehouse.
    This prevents a single long-running transaction.
    """
    warehouse_ids = Warehouse.objects.filter(is_active=True).values_list('id', flat=True)
    count = 0
    for w_id in warehouse_ids:
        run_warehouse_reconciliation.delay(w_id)
        count += 1
    return f"Triggered reconciliation for {count} warehouses"

@shared_task(time_limit=600) # 10 mins soft limit per warehouse
def run_warehouse_reconciliation(warehouse_id):
    """
    WORKER TASK:
    Reconciles inventory for a SINGLE warehouse.
    Uses pagination to process SKUs in small chunks to keep memory low.
    """
    logger.info(f"Reconciling Warehouse {warehouse_id}...")
    
    stocks = InventoryStock.objects.filter(warehouse_id=warehouse_id).select_related('product')
    paginator = Paginator(stocks, 1000) # Process 1000 SKUs at a time
    
    mismatch_count = 0
    
    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        
        # Iterate over the chunk
        for stock in page.object_list:
            # Atomic block PER ITEM (or per small batch) is safer than per warehouse
            # checking logic...
            
            with transaction.atomic():
                # Sum Physical Bins
                physical_sum = BinInventory.objects.filter(
                    bin__zone__warehouse_id=warehouse_id,
                    sku=stock.product
                ).aggregate(total=Sum('quantity'))['total'] or 0
                
                # Compare
                if stock.quantity != physical_sum:
                    diff = physical_sum - stock.quantity
                    
                    logger.warning(
                        f"Mismatch {stock.warehouse.code} | {stock.product.sku_code}: "
                        f"Logical={stock.quantity} != Physical={physical_sum}"
                    )
                    
                    # Auto-Correct
                    stock.quantity = physical_sum
                    stock.save(update_fields=['quantity'])
                    
                    # Log Audit Trail
                    StockMovementLog.objects.create(
                        inventory=stock,
                        quantity_change=diff,
                        movement_type=StockMovementLog.MovementType.RECONCILIATION,
                        reference="SYSTEM_RECON",
                        balance_after=physical_sum
                    )
                    mismatch_count += 1

    return f"WH {warehouse_id}: Reconciled. Fixed {mismatch_count} mismatches."